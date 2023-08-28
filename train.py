import chess
from neo4j import GraphDatabase
import torch
import torch.nn.functional as F
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset
from torch.utils.data import DataLoader
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

# convert 1x64 into 8x8 matrix ( same with one in evaluate.py )
def formMat(arr):
    temp = []
    ttemp = []
    for idx, item in enumerate(arr):
        ttemp.append(item)
        if ( idx % 8 == 7 ):
            temp.append(ttemp)
            ttemp = []
    return temp

# encode FEN to do ML ( same with one in evaluate.py )
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


    return x

# get digit number corresponding to the given square ('a1', 'b2' , etc..)
def getBoardIndex(square):
    global zz
    return zz.get(square)



# simple dataset
class MyDataSet(Dataset):
    def __init__(self,x,y, device):
        self.x = x
        self.y = y
        self.device = device

    def __getitem__(self, index):
        x = torch.FloatTensor(self.x[index]).to(self.device)
        y = torch.LongTensor([self.y[index]]).to(self.device)

        return x, y

    def __len__(self):
        return len(self.x)


# do learning
def train(session, from_model, to_model):

    ###
    batch_size = 2048
    lr = 1e-5
    epochs = 500
    ###


    # q = '''MATCH (f:Position { turn : 1 , color : "''' + comSide + '''" })-[m:Move]->(:Position) 
    # RETURN f.fen, m.uci, m.win, m.draw, (m.win + m.draw + m.lose) as games'''
    q = '''MATCH (f:Position { turn : 1 })-[m:Move]->(:Position) 
    RETURN f.fen, m.uci, m.win, m.draw, (m.win + m.draw + m.lose) as games'''
    l = list(session.run(q))


    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(777)
    if device == 'cuda':
        torch.cuda.manual_seed_all(777)
    print(f"device : {device}")

    x = []
    y_from = []
    y_to = []

    for item in l:
        frm = item["m.uci"][:2]
        to = item["m.uci"][2:4]

        frm_index = getBoardIndex(frm)
        to_index = getBoardIndex(to)
        if ( ( item["m.win"] + item["m.draw"] )/ item["games"] > 0.6 ):
            for i in range(item["games"]):
                x.append(encodeFEN(item["f.fen"]))
                # y.append(oneHotEncoding(item["m.uci"]))
                y_from.append(frm_index)
                y_to.append(to_index)


    dataset_from = MyDataSet(x,y_from,device)
    dataset_to = MyDataSet(x,y_to,device)

    dataloader_from = DataLoader(dataset_from, batch_size=batch_size)
    dataloader_to = DataLoader(dataset_to, batch_size=batch_size)

    ####### whether learning from scratch or not ###

    # model_from = CNN.ChessNet().to(device)
    # model_to = CNN.ChessNet().to(device)

    model_from = torch.load(from_model)
    model_to = torch.load(to_model)

    #####

    model_from.train()
    model_to.train()
    
    criterion_from = nn.CrossEntropyLoss().to(device)
    optitmizer_from = optim.Adam(model_from.parameters(), lr= lr)

    criterion_to = nn.CrossEntropyLoss().to(device)
    optitmizer_to = optim.Adam(model_to.parameters(), lr = lr)

    for epoch in range(epochs+1):
        for batch_idx, samples in enumerate(dataloader_from):
            optitmizer_from.zero_grad()

            X, Y = samples
            Y = Y.view(-1)
            hypothesis = model_from(X)
            cost_from = criterion_from(hypothesis, Y)

            cost_from.backward()
            optitmizer_from.step()

        for batch_idx, samples in enumerate(dataloader_to):
            optitmizer_to.zero_grad()
            
            X, Y = samples
            Y = Y.view(-1)
            hypothesis = model_to(X)
            cost_to = criterion_to(hypothesis, Y)

            cost_to.backward()
            optitmizer_to.step()

        
        print(f"{epoch}/{epochs} _ cost_from : {cost_from.item()} _ cost_to : {cost_to.item()}")


    torch.save(model_from,from_model)
    torch.save(model_to,to_model)

    return model_from,model_to, device



