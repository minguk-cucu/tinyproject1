from neo4j import GraphDatabase
import chess
import random
import train
import evaluate
import torch
import torch.nn as nn
import torch.nn.functional as F
import threading
import time
from CNN import CNN

############
username = 'Hikaru'
gameType = 'blitz'
rule = 'chess'
############




####

# Check if a game could be end
def checkGameEnd(color):
    global board
    
    if(board.is_checkmate()):
        print("Game End by Checkmate",end='')
        if color == 'WHITE' : print(" 1-0")
        if color == 'BLACK' : print(" 0-1")
        print ("bye !")
        exit(0)
    if(board.is_stalemate()):
        print("Game End by Stalemate 0.5-0.5")
        print ("bye !")
        exit(0)
    if(board.is_insufficient_material()):
        print("Game End by Insufficient Material to make Checkmate 0.5-0.5")
        print("bye !")
        exit(0)
    if(board.can_claim_draw()):
        print("Can Claim Draw")
    if(board.can_claim_threefold_repetition()):
        print("Can Claim Three-Fold-Repetition")
    if(board.can_claim_fifty_moves()):
        print("Can Claim Fifty-Move-Draw")

# If a move is in DB, do Our own algorithm.
def doOwnAlgorithm():
    global board

    winRate=[]
    dwinRate=[]

    q = 'MATCH (f:Position { fen : "' + board.fen() + '" , color : "' + comSide + '"} )-[m:Move]->(:Position) return m.san, m.win, m.lose, m.draw'
    moveList = list(session.run(q))
    for move in moveList:
        win = move["m.win"]
        lose = move["m.lose"]
        draw = move["m.draw"]
        whole = win+lose+draw
        winRate.append((win / whole, whole)) # win rate --> (rate, denominator)
        dwinRate.append(((win + draw) / whole , whole)) # ( win + draw ) rate --> (rate, denominator)

    p = pickOne(winRate,0.5)
    if ( p == -1 ): p = pickOne(dwinRate,0.5)
    if ( p == -1 ): p = pickOne(winRate,0.4)
    if ( p == -1 ): p = pickOne(dwinRate,0.4)
    if ( p == -1 ): p = pickOne(dwinRate,0.3)
    if ( p == -1 ): p = pickOne(dwinRate,0.0)
    if ( p == -1 ): 
        #p = pickOne(dwinRate,-1) # pick anything in my DB. ( instead, how about pick one from general DB ? or do ML )
        doML()
    else:
        print(moveList[p]["m.san"])
        board.push_san(moveList[p]["m.san"])

# Pick one of several moves that meet the criteria.
def pickOne(arr, rate): # pick one of items ( > rate // greater than rate )
    idxList = [] # resultList[idx][data]
    for idx, raw in enumerate(arr):
        if ( raw[0] > rate):
            idxList.append(idx)
        else:
            continue
    if (len(idxList) == 0): return -1
    if (len(idxList) == 1): return idxList[0] # return idx of picked one ( should be converted by moveList[x]["m.san"])

    sum = 0
    for idx in idxList: # summation of number of games
        sum += arr[idx][1]
    rint = random.randrange(0,sum) # do lottery
    isum = 0
    for idx in idxList:
        isum += arr[idx][1]
        if ( rint < isum ):
            return idx  # return idx of picked one ( should be converted by moveList[x]["m.san"])

# If a move is NOT in DB, we do ML ( not actually do it in this function, just named ) 
def doML():
    p = evaluate.getBestMove(board.fen(), model_from,model_to, device)
    print(f"ML : {p}")
    board.push_uci(p)

# Convert games into Graph
def convertMoves(color):
    if ( color == 'WHITE' ):
        print("WHITE encoding . . .")
        q = 'MATCH (g:Game { whiteUser : "' + username +'"} ) RETURN g.moves' ## WHEN YOU PLAYED WHITE ONE ##########
        nodes = list(session.run(q))
        board = chess.Board()
        q = 'MATCH ( f:Position { triv : "initial" , color : "WHITE"} ) RETURN f'
        if (len(list(session.run(q))) == 0 ):
            q = 'MERGE ( f:Position { fen : "' + board.fen() + '", triv : "initial", color : "WHITE", win : 0, draw : 0, lose : 0, turn : 1} )'
            session.run(q)

        for idx, move in enumerate(nodes):
            board = chess.Board()
            arr = move[0].split()
            turn = 1
            for i in range(1,len(arr),2): # len (arr) -> always be even ( 1.e4 2.e5 )
                fen_before = board.fen()
                uci = board.push_san(arr[i])
                q = '''
                    MATCH (bf:Position { fen : "''' + fen_before + '''", color : "WHITE"} ) '''
                if ( turn == 1 ):
                    q +=  '''MERGE ( f:Position { fen : "''' + board.fen() + '''", color : "WHITE", win : 0, draw : 0, lose : 0, turn : 0} )
                    MERGE (bf)-[m:Move { san : "''' + arr[i] + '''", uci : "''' + str(uci) + '''", color : "WHITE", win : 0, draw : 0, lose : 0 }]-(f)'''
                    turn = 0
                else:
                    q +=  '''MERGE ( f:Position { fen : "''' + board.fen() + '''", color : "WHITE", win : 0, draw : 0, lose : 0, turn : 1} )
                    MERGE (bf)-[m:Move { san : "''' + arr[i] + '''", uci : "''' + str(uci) + '''", color : "WHITE", win : 0, draw : 0, lose : 0 }]-(f)'''
                    turn = 1
                session.run(q)

            print(f"playing in WHITE(1/2) - {idx+1}/{len(list(nodes))} progress .. ")

        for idx, move in enumerate(nodes):
            board = chess.Board()
            q = 'MATCH (g:Game { moves : "'+ move[0] + '" } ) return g.whiteResult'
            result = list(session.run(q))[0]["g.whiteResult"]
            if ( result == "win" ): # white won
                conclude = "win"
            elif( result == "checkmated" or  result == "resinged" or result == "timeout" or 
                  result == "lose" or result == "abandoned" ) : # white lost
                conclude = "lose"
            else: # draw
                conclude = "draw"

            arr = move[0].split()
            q = 'MATCH ( f:Position { fen :"' + board.fen() +'", color : "WHITE" }) SET f.'+conclude+' = f.' +conclude +' + 1 RETURN f'
            session.run(q)
            for i in range(1, len(arr), 2):
                q = '''
                    MATCH ( bf:Position { fen : "'''+ board.fen() +'''", color : "WHITE" })-[m:Move { san : "''' + arr[i] +'''"}]->(f:Position)
                    SET m.'''+conclude+''' = m.'''+conclude+''' +1 
                    SET f.'''+conclude+''' = f.'''+conclude+''' +1
                    RETURN f'''
                session.run(q)
                board.push_san(arr[i])

            print(f"playing in WHITE(2/2) - {idx+1}/{len(list(nodes))} progress .. ")

            
    elif ( color == 'BLACK' ):
        print("BLACK encoding . . .")
        q = 'MATCH (g:Game { blackUser : "' + username +'"} ) RETURN g.moves' ## WHEN YOU PLAYED BLACK ONE ##########
        nodes = list(session.run(q))
        board =chess.Board()
        q = 'MATCH ( f:Position { triv : "initial" , color : "BLACK"} ) RETURN f'
        if (len(list(session.run(q))) == 0 ):
            q = 'MERGE ( f:Position { fen : "' + board.fen() + '", triv : "initial", color : "BLACK", win : 0, draw : 0, lose : 0, turn : 0} )'
            session.run(q)
        for idx, move in enumerate(nodes):
            board = chess.Board()

            arr = move[0].split()
            turn = 0
            for i in range(1,len(arr),2): # len (arr) -> always be even ( 1.e4 2.e5 )
                fen_before = board.fen()
                uci = board.push_san(arr[i])
                q = '''
                    MATCH (bf:Position { fen : "''' + fen_before + '''", color : "BLACK"} )'''

                if ( turn == 1 ):
                    q += '''MERGE ( f:Position { fen : "''' + board.fen() + '''", color : "BLACK", win : 0, draw : 0, lose : 0, turn : 0 } )
                    MERGE (bf)-[m:Move { san : "''' + arr[i] + '''", uci : "''' + str(uci) + '''", color : "BLACK", win : 0, draw : 0, lose : 0 }]-(f)'''
                    turn = 0
                else:
                    q += '''MERGE ( f:Position { fen : "''' + board.fen() + '''", color : "BLACK", win : 0, draw : 0, lose : 0, turn : 1 } )
                    MERGE (bf)-[m:Move { san : "''' + arr[i] + '''", uci : "''' + str(uci) + '''", color : "BLACK", win : 0, draw : 0, lose : 0 }]-(f)'''
                    turn = 1                    
                session.run(q)
            print(f"playing in BLACK(1/2) - {idx+1}/{len(list(nodes))} progress .. ")

        for idx, move in enumerate(nodes):
            board = chess.Board()
            q = 'MATCH (g:Game { moves : "'+ move[0] + '" } ) return g.blackResult'
            result = list(session.run(q))[0]["g.blackResult"]
            if ( result == "win" ): # black won
                conclude = "win"
            elif( result == "checkmated" or  result == "resinged" or result == "timeout" or 
                  result == "lose" or result == "abandoned" ) : # black lost
                conclude = "lose"
            else: # draw
                conclude = "draw"

            arr = move[0].split()
            q = 'MATCH ( f:Position { fen :"' + board.fen() +'", color : "BLACK" }) SET f.'+conclude+' = f.' +conclude +' + 1 RETURN f'
            session.run(q)
            for i in range(1, len(arr), 2):
                q = '''
                    MATCH ( bf:Position { fen : "'''+ board.fen() +'''", color : "BLACK" })-[m:Move { san : "''' + arr[i] +'''"}]->(f:Position)
                    SET m.'''+conclude+''' = m.'''+conclude+''' +1 
                    SET f.'''+conclude+''' = f.'''+conclude+''' +1
                    RETURN f'''
                session.run(q)
                board.push_san(arr[i])

            print(f"playing in BLACK(2/2) - {idx+1}/{len(list(nodes))} progress .. ")

    else :
        #error
        print("COLOR must be WHITE or BLACK ( in CAPITAL form)")


    


#################################### main ###############################################
driver = GraphDatabase.driver('bolt://localhost:7687', auth = ('neo4j', 'bruce89p13'))
session = driver.session()


# q = 'MATCH ( g:Game ) DELETE g'
# session.run(q)

# q = 'CREATE INDEX position_att IF NOT EXISTS FOR (f:Position) ON (f.fen, f.win, f.lose, f.draw, f.color, f.turn)'
# session.run(q)
# q = 'CREATE INDEX move_att IF NOT EXISTS FOR (m:Move) ON (m.uci, m.san, m.color, m.win, m.lose, m.draw)'
# session.run(q)

# print("Fetching from Chess.com database")

# q = '''UNWIND [ "2023/02" ] as ym
#  WITH ("https://api.chess.com/pub/player/''' + username + '''/games/" + ym) as url
#  CALL apoc.load.json(url) YIELD value
#  UNWIND value.games as game
#  WITH game.time_class as type, game.pgn as raw, game.white.result as whiteResult, game.white.username as whiteUser, game.black.result as blackResult, game.black.username as blackUser, game.rules as rule
#  WHERE type = "''' + gameType + '''" AND rule = "''' + rule + '''"
#  WITH whiteUser, whiteResult, blackUser, blackResult, apoc.text.replace(coalesce(apoc.text.regexGroups(raw, "(\\n\\n)(.+)( (0|1|(1/2))-(0|1|(1/2)))")[0][2], ""), "(\\{.{1,17}\\})", "") as moves
#  WHERE moves <> ""
#  MERGE (g:Game { whiteUser: whiteUser, whiteResult: whiteResult, blackUser: blackUser, blackResult: blackResult, moves: moves })'''

# session.run(q)

# print("Fetching games from Chess.com has Done !")
# t1 = time.time()
# print("Convert Games into Graph . . . ")
# board =chess.Board()

# convertMoves("WHITE")
# convertMoves("BLACK")


# print("Converting has Done !")
# t2 = time.time()
# print(f"Converting time : {t2-t1} s")
#######################################################


## ML ##
t1 = time.time()
print("doing ML based on your records . . ")

model_from,model_to, device = train.train(session, 'WHITE')
# model_from = torch.load(".\\model_from_.pt")
# model_to = torch.load(".\\model_to_.pt")
# device = "cuda"

print("ML done")
t2 = time.time()
print(f"ML time : {t2-t1} s")

model_from.eval()
model_to.eval()
####

# play a game
while(1):
    playerSide = input("Which side would you like to play ? : 1. WHITE 2. BLACK ( you can either choose number ( 1 or 2 ) or type color ( WHITE or BLACK) : ")
    if ( playerSide == "WHITE" or playerSide == "BLACK" or playerSide == "1" or playerSide == "2" ):
        break
    else:
        print("You should give answer in a proper way")


#PLAYER plays WHITE
#COM plays BLACK
if ( playerSide == "WHITE" or playerSide == "1" ):

    playerSide = "WHITE"
    comSide = "BLACK"

    board = chess.Board()
    q = 'MATCH (f:Position { triv : "initial", color : "BLACK" }) RETURN f'
    if len(list(session.run(q))) == 0:
        #error
        print("There is no data with Starting Position == ERROR")
        exit(-1)
    else:
        #on the way
        print(board)
        
        playersMove = input("Your Move : ")
        ## here, there must be Legal Move check. but chess.py does it automatically
        while(playersMove not in str(board.legal_moves)):
            playersMove = input("Your Move is illegal, please do proper move : ")
        board.push_san(playersMove)

        checkGameEnd("WHITE")
        print(board)

        doOwnAlgorithm()
        checkGameEnd('BLACK')

        print(board)
        while(1):
            playersMove = input("Your Move : ")
            while(playersMove not in str(board.legal_moves)):
                playersMove = input("Your Move is illegal, please do proper move : ")
            ## here, there must be Legal Move check.
            board.push_san(playersMove)
            print(board)
            checkGameEnd('WHITE')
            
            

            q = 'MATCH (f:Position { fen : "' + board.fen() + '", color : "BLACK"}) RETURN f'
            if len(list(session.run(q))) == 0:
                # there is no data with current position in DB. do ML
                doML()
            else:
                # My Own Algorithm
                doOwnAlgorithm()

            print(board)
            checkGameEnd('BLACK')

#PLAYER plays BLACK
#COM plays WHITE
if ( playerSide == "BLACK" or playerSide == "2" ):

    playerSide = "BLACK"
    comSide = "WHITE"

    board = chess.Board()
    q = 'MATCH (f:Position { triv : "initial", color : "WHITE" }) RETURN f'
    if len(list(session.run(q))) == 0:
        # error
        print("There is no data with Starting Position == ERROR")
        exit(-1)
    else:
        #on the way
        doOwnAlgorithm()

        print(board)
        checkGameEnd('WHITE')
        
        playersMove = input("Your Move : ")
        ## here, there must be Legal Move check. but chess.py does it automatically
        while(playersMove not in str(board.legal_moves)):
            playersMove = input("Your Move is illegal, please do proper move : ")
        board.push_san(playersMove)
        
        print(board)
        checkGameEnd('BLACK')
        
        
        while(1):
            q = 'MATCH (f:Position { fen : "' + board.fen() + '", color : "WHITE"}) RETURN f'
            if len(list(session.run(q))) == 0:
                # there is no data with current position in DB. do ML
                doML()
            else:
                # My Own Algorithm
                doOwnAlgorithm()

            print(board)
            checkGameEnd('WHITE')
        
            playersMove = input("Your Move : ")
            ## here, there must be Legal Move check.
            while(playersMove not in str(board.legal_moves)):
                playersMove = input("Your Move is illegal, please do proper move : ")
            board.push_san(playersMove)    
            
            print(board)
            checkGameEnd('BLACK')
 


session.close()

