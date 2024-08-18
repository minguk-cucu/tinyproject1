import torch
import torch.nn as nn
import torch.nn.functional as F

class CNN(nn.Module):
    def __init__(self):
        super(CNN,self).__init__()
        self.conv1 = nn.Conv2d(200, 200, kernel_size=3, stride=1, padding=1)
        self.conv2 = nn.Conv2d(200, 200, kernel_size=3, stride=1, padding=1)
        self.bn1 = nn.BatchNorm2d(200)
        self.bn2 = nn.BatchNorm2d(200)
        self.act1 = nn.SELU()
        self.act2 = nn.SELU()
    
    def forward(self, x):
        x_input = torch.clone(x)
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.act1(x)
        x = self.conv2(x)
        x = self.bn2(x)
        x = x + x_input
        x = self.act2(x)

        return x

class ChessNet(nn.Module):
    def __init__(self):
        super(ChessNet,self).__init__()
        self.hLayers = 4
        self.hSize = 200
        self.inLayers = nn.Conv2d(14, self.hSize, 3, stride=1, padding=1)
        self.mList = nn.ModuleList([CNN() for i in range(self.hLayers)])
        self.oLayers = nn.Conv2d(self.hSize, 14, 3, stride=1, padding=1)
        self.fc = nn.Linear(8 * 8 * 14, 64*64, bias=True)

    def forward(self, x):
        x = self.inLayers(x)
        x = F.relu(x)

        for i in range(self.hLayers):
            x = self.mList[i](x)

        x = self.oLayers(x)
        x = x.view(x.size(0), -1) 
        x = self.fc(x)

        return x

