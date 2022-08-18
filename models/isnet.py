import torch
import torch.nn as nn
from collections import OrderedDict
import torch
from torch.functional import norm
import torch.nn as nn
import torch.nn.functional as F
from torchvision.models import vgg16, vgg16_bn
from torchvision.models import resnet50

from models.modules import ResBlk
from models.pvt import pvt_v2_b2
from config import Config


bce_loss = nn.BCELoss(size_average=True)
def muti_loss_fusion(preds, target):
    loss0 = 0.0
    loss = 0.0

    for i in range(0,len(preds)):
        # print("i: ", i, preds[i].shape)
        if(preds[i].shape[2]!=target.shape[2] or preds[i].shape[3]!=target.shape[3]):
            # tmp_target = _upsample_like(target,preds[i])
            tmp_target = F.interpolate(target, size=preds[i].size()[2:], mode='bilinear', align_corners=True)
            loss = loss + bce_loss(preds[i],tmp_target)
        else:
            loss = loss + bce_loss(preds[i],target)
        if(i==0):
            loss0 = loss
    return loss0, loss

fea_loss = nn.MSELoss(size_average=True)
kl_loss = nn.KLDivLoss(size_average=True)
l1_loss = nn.L1Loss(size_average=True)
smooth_l1_loss = nn.SmoothL1Loss(size_average=True)
def muti_loss_fusion_kl(preds, target, dfs, fs, mode='MSE'):
    loss0 = 0.0
    loss = 0.0

    for i in range(0,len(preds)):
        # print("i: ", i, preds[i].shape)
        if(preds[i].shape[2]!=target.shape[2] or preds[i].shape[3]!=target.shape[3]):
            # tmp_target = _upsample_like(target,preds[i])
            tmp_target = F.interpolate(target, size=preds[i].size()[2:], mode='bilinear', align_corners=True)
            loss = loss + bce_loss(preds[i],tmp_target)
        else:
            loss = loss + bce_loss(preds[i],target)
        if(i==0):
            loss0 = loss

    for i in range(0,len(dfs)):
        if(mode=='MSE'):
            loss = loss + fea_loss(dfs[i],fs[i]) ### add the mse loss of features as additional constraints
            # print("fea_loss: ", fea_loss(dfs[i],fs[i]).item())
        elif(mode=='KL'):
            loss = loss + kl_loss(F.log_softmax(dfs[i],dim=1),F.softmax(fs[i],dim=1))
            # print("kl_loss: ", kl_loss(F.log_softmax(dfs[i],dim=1),F.softmax(fs[i],dim=1)).item())
        elif(mode=='MAE'):
            loss = loss + l1_loss(dfs[i],fs[i])
            # print("ls_loss: ", l1_loss(dfs[i],fs[i]))
        elif(mode=='SmoothL1'):
            loss = loss + smooth_l1_loss(dfs[i],fs[i])
            # print("SmoothL1: ", smooth_l1_loss(dfs[i],fs[i]).item())

    return loss0, loss


class ISNetDIS(nn.Module):
    def __init__(self):
        super(ISNetDIS, self).__init__()
        self.config = Config()
        bb = self.config.bb
        if bb == 'cnn-vgg16':
            bb_net = list(vgg16(pretrained=True).children())[0]
            bb_convs = OrderedDict({
                'conv1': bb_net[:4],
                'conv2': bb_net[4:9],
                'conv3': bb_net[9:16],
                'conv4': bb_net[16:23]
            })
        elif bb == 'cnn-vgg16bn':
            bb_net = list(vgg16_bn(pretrained=True).children())[0]
            bb_convs = OrderedDict({
                'conv1': bb_net[:6],
                'conv2': bb_net[6:13],
                'conv3': bb_net[13:23],
                'conv4': bb_net[23:33]
            })
        elif bb == 'cnn-resnet50':
            bb_net = list(resnet50(pretrained=True).children())
            bb_convs = OrderedDict({
                'conv1': nn.Sequential(*bb_net[0:3]),
                'conv2': bb_net[4],
                'conv3': bb_net[5],
                'conv4': bb_net[6]
            })
        elif bb == 'trans-pvt':
            self.bb = pvt_v2_b2()
            if self.config.pvt_weights:
                save_model = torch.load(self.config.pvt_weights)
                model_dict = self.bb.state_dict()
                state_dict = {k: v for k, v in save_model.items() if k in model_dict.keys()}
                model_dict.update(state_dict)
                self.bb.load_state_dict(model_dict)

        if 'cnn-' in bb:
            self.bb = nn.Sequential(bb_convs)
        lateral_channels_in = {
            'cnn-vgg16': [512, 256, 128, 64],
            'cnn-vgg16bn': [512, 256, 128, 64],
            'cnn-resnet50': [1024, 512, 256, 64],
            'trans-pvt': [512, 320, 128, 64],
        }

        if self.config.dec_blk == 'ResBlk':
            DecBlk = ResBlk

        self.top_layer = DecBlk(lateral_channels_in[bb][0], lateral_channels_in[bb][1])

        self.dec_layer4 = DecBlk(lateral_channels_in[bb][1], lateral_channels_in[bb][1])
        self.lat_layer4 = nn.Conv2d(lateral_channels_in[bb][1], lateral_channels_in[bb][1], 1, 1, 0)

        self.dec_layer3 = DecBlk(lateral_channels_in[bb][1], lateral_channels_in[bb][2])
        self.lat_layer3 = nn.Conv2d(lateral_channels_in[bb][2], lateral_channels_in[bb][2], 1, 1, 0)

        self.dec_layer2 = DecBlk(lateral_channels_in[bb][2], lateral_channels_in[bb][3])
        self.lat_layer2 = nn.Conv2d(lateral_channels_in[bb][3], lateral_channels_in[bb][3], 1, 1, 0)

        self.dec_layer1 = DecBlk(lateral_channels_in[bb][3], lateral_channels_in[bb][3]//2)
        self.conv_out1 = nn.Sequential(nn.Conv2d(lateral_channels_in[bb][3]//2, 1, 1, 1, 0))

    def compute_loss_kl(self, preds, targets, dfs, fs, mode='MSE'):

        # return muti_loss_fusion(preds,targets)
        return muti_loss_fusion_kl(preds, targets, dfs, fs, mode=mode)

    def compute_loss(self, preds, targets):

        # return muti_loss_fusion(preds,targets)
        return muti_loss_fusion(preds, targets)


    def forward(self, x):
        ########## Encoder ##########

        if 'trans' in self.config.bb:
            x1, x2, x3, x4 = self.bb(x)
        else:
            x1 = self.bb.conv1(x)
            x2 = self.bb.conv2(x1)
            x3 = self.bb.conv3(x2)
            x4 = self.bb.conv4(x3)

        p4 = self.top_layer(x4)

        ########## Decoder ##########
        scaled_preds = []

        p4 = self.dec_layer4(p4)
        p4 = F.interpolate(p4, size=x3.shape[2:], mode='bilinear', align_corners=True)
        p3 = p4 + self.lat_layer4(x3)

        p3 = self.dec_layer3(p3)
        p3 = F.interpolate(p3, size=x2.shape[2:], mode='bilinear', align_corners=True)
        p2 = p3 + self.lat_layer3(x2)

        p2 = self.dec_layer2(p2)
        p2 = F.interpolate(p2, size=x1.shape[2:], mode='bilinear', align_corners=True)
        p1 = p2 + self.lat_layer2(x1)

        p1 = self.dec_layer1(p1)
        p1 = F.interpolate(p1, size=x.shape[2:], mode='bilinear', align_corners=True)
        p1_out = self.conv_out1(p1)
        scaled_preds.append(torch.sigmoid(p1_out))

        return scaled_preds, None
