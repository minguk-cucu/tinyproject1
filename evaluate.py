import chess
from neo4j import GraphDatabase
import torch
import torch.nn.functional as F
import torch.nn as nn
import torch.optim as optim
import CNN


moves = [ 'a8', 'b8', 'c8', 'd8', 'e8', 'f8', 'g8', 'h8',
          'a7', 'b7', 'c7', 'd7', 'e7', 'f7', 'g7', 'h7',
          'a6', 'b6', 'c6', 'd6', 'e6', 'f6', 'g6', 'h6',
          'a5', 'b5', 'c5', 'd5', 'e5', 'f5', 'g5', 'h5',
          'a4', 'b4', 'c4', 'd4', 'e4', 'f4', 'g4', 'h4',
          'a3', 'b3', 'c3', 'd3', 'e3', 'f3', 'g3', 'h3',
          'a2', 'b2', 'c2', 'd2', 'e2', 'f2', 'g2', 'h2',
          'a1', 'b1', 'c1', 'd1', 'e1', 'f1', 'g1', 'h1',]
zz = dict(zip(moves,range(0,64)))

# convert 1x64 into 8x8 matrix ( same with one in train.py )
def formMat(arr):
    temp = []
    ttemp = []
    for idx, item in enumerate(arr):
        ttemp.append(item)
        if ( idx % 8 == 7 ):
            temp.append(ttemp)
            ttemp = []
    return temp

# encode FEN to do ML ( same with one in train.py )
def encodeFEN(fen):
    board = chess.Board(fen)

    arr = fen.split()
    x = []
    br = [0]*64
    bn = [0]*64
    bb = [0]*64
    bq = [0]*64
    bk = [0]*64
    bp = [0]*64
    wr = [0]*64
    wn = [0]*64
    wb = [0]*64
    wq = [0]*64
    wk = [0]*64
    wp = [0]*64



    i = 0
    for s in arr[0]:
        if ( s == "r"):
            br[i] = -5
        if ( s == "n"):
            bn[i] = -3
        if ( s == "b"):
            bb[i] = -3
        if ( s == "q"):
            bq[i] = -9
        if ( s == "k"):
            bk[i] = -99
        if ( s == "p"):
            bp[i] = -1
        if ( s == "R"):
            wr[i] = 5
        if ( s == "N"):
            wn[i] = 3
        if ( s == "B"):
            wb[i] = 3
        if ( s == "Q"):
            wq[i] = 9
        if ( s == "K"):
            wk[i] = 99
        if ( s == "P"):
            wp[i] = 1
        if ( s == '/'):
            continue
        if ( '0' <= s <= '9'):
            i += int(s)
            continue
        i += 1

    x.append(formMat(br))
    x.append(formMat(bn))
    x.append(formMat(bb))
    x.append(formMat(bq))
    x.append(formMat(bk))
    x.append(formMat(bp))
    x.append(formMat(wr))
    x.append(formMat(wn))
    x.append(formMat(wb))
    x.append(formMat(wq))
    x.append(formMat(wk))
    x.append(formMat(wp))
    

    b_attaking = [0]*64
    w_attaking = [0]*64

    for i in range(0,64):
        if ( len(board.attackers(chess.BLACK, i)) != 0 ):
            b_attaking[i] = 1
        if ( len(board.attackers(chess.WHITE,i)) != 0 ):
            w_attaking[i] = 1


    b_attaking = formMat(b_attaking)
    b_attaking.reverse()    

    w_attaking = formMat(w_attaking)
    w_attaking.reverse()

    x.append(b_attaking)
    x.append(w_attaking)

    ##
    # if( arr[1] == 'w'): # WHITE = 1
    #     temp = [1] * 64
    #     x.append(formMat(temp))
    # else:
    #     temp = [0] * 64
    #     x.append(formMat(temp)) # BLACK = 0

    # castle = [0]*4 # castle[0] -> white short [1] -> white long [2] -> black short [3] -> black long
    # for s in arr[2]:
    #     if ( s == "K" ):
    #         castle[0] = 1
    #     if ( s == "Q" ):
    #         castle[1] = 1
    #     if ( s == "k" ):
    #         castle[2] = 1
    #     if ( s == "q" ):
    #         castle[3] = 1

    # x.append(castle)
    # ##

    # enp = [0]*64 # en_passant

    # if( arr[3] != "-"):
    #     enp[getBoardIndex(arr[3])] = 1

    # x.append(enp)
    # ##

    # x.append(int(arr[4]))
    # x.append(int(arr[5]))

    return x


# literally get best move a engine could play
def getBestMove(fen, model, device):
    x = torch.FloatTensor(encodeFEN(fen)).to(device)
    x = x.view(1,14,8,8) # notice its channel must be adjusted as CNN changes
    
    board = chess.Board(fen)



    legalM = []
    for i in list(board.legal_moves):
        legalM.append(str(i))

    fromToList = model(x)

       


    tensorValueList = []
    for i in legalM:
        i[:2] #from
        i[2:] #to
        value = fromToList[0][zz.get(i[:2])*64+zz.get(i[2:])]
        tensorValueList.append((i , value ))
    

    tensorValueList.sort(key=lambda x:x[1])
    print(tensorValueList)

    return tensorValueList[-1][0]

