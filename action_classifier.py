import numpy as np

import torch
import torch.nn as nn
from PIL import Image
from model.i3dpt import I3D, Unit3Dpy
from torchvision import transforms as  T
import time


class ActionClassifier:
    def __init__(self, model_path, temporal_batch_size=24, img_size=224):
        
        #self.classes = ['non-touching', 'touching']
        #self.classes = ['touching', 'non-touching']
        
        # drinking, touching_phone, touching_keyboard
        self.classes = ['drinking', 'picking_up_phone', 'removing_mask',
                        'resting_chin_on_hand', 'rubbing_eyes', 'touching_glasses',
                        'touching_hairs', 'touching_keyboard', 'touching_nose', 
                        'touching_phone', 'wearing_mask']
        
        # define action
        self.touching_actions = ['picking_up_phone', 'resting_chin_on_hand', 'rubbing_eyes', 'touching_hairs',
                                    'touching_nose']


        # b, c, w, h
        self.model = I3D(num_classes=400, modality='rgb')
        #self.I3D = nn.DataParallel(self.model)

        self.model.conv3d_0c_1x1 = self._modify_lastlayer(self.model.conv3d_0c_1x1, out_ch=len(self.classes))
        self.model.softmax = torch.nn.Softmax()
        #self.model.softmax = torch.nn.Sigmoid()
        
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model.to(self.device)
        self.model.eval()
        print(self.device)
        if self.device is 'cuda':
            state_dict = self._change_key(torch.load(model_path))
        else:
            state_dict = self._change_key(torch.load(model_path, map_location=torch.device('cpu')))
        self.model.load_state_dict(state_dict)


        self.temporal_batch_size = temporal_batch_size
        self.temporal_batch = torch.zeros((1, 3, self.temporal_batch_size, img_size, img_size)) 
        self.transforms = T.Compose([
            T.Resize((img_size,img_size)),
            T.ToTensor(),
            T.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
            ])

        self.pred = None
        self.need_sleep = False
        self.cnt = 0
    
    def _set_param_requires_grad(self, feature_extracting, training_num):
        if feature_extracting:
            for i, param in enumerate(self.model.parameters()):
                if training_num >= i:
                    param.requires_grad = False


    def _modify_lastlayer(self, last_layer, out_ch):
        conv2 = Unit3Dpy(in_channels=400, out_channels=len(self.classes),
                        kernel_size=(1, 1, 1), activation=None, use_bias=True, use_bn=False)
        branch_0 = torch.nn.Sequential(last_layer, conv2)
        return branch_0

    def _change_key(self, ord_dict):
        state_dict = ord_dict.copy()

        for i, key in enumerate(ord_dict.keys()):
            key, value = state_dict.popitem(False)
            old = key
            state_dict[key.replace('module.', '') if key == old else key] = value

        return state_dict

    def run(self, img):

        # conver image to tensor
        pil_img = Image.fromarray(img)
        img_tensor = self.transforms(pil_img)
        
        if self.need_sleep is False:
            self.temporal_batch[:, :, self.cnt, :, :] = img_tensor
        
        # every 16 frames, input image to network
        if (self.cnt == self.temporal_batch_size-1) & (self.need_sleep is False):
            start_time = time.time()
            self.temporal_batch = self.temporal_batch.to(self.device)
            out_var, out_logit = self.model(self.temporal_batch)
            out = torch.nn.functional.softmax(out_logit, 1).data.cpu()
            top_val, top_idx = torch.sort(out, 1, descending=True)
            end_time = time.time()
            print('inference time: ',  end_time-start_time)
             
            self.pred = self.classes[int(top_idx[0,0].data.numpy())]
            self.score = top_val[0,0].data.numpy()
            print(self.score, self.pred)
            if (self.pred in self.touching_actions) & (self.score > 0.9) :
                self.pred = '얼굴을 만지지 마세요 !'
            else:
                self.pred = '' 
            
            #self.need_sleep = True
            self.cnt = 0
        
        '''        
        if (self.cnt == 10) & (self.need_sleep is True):
            self.need_sleep = False
            self.cnt = 0
        '''
            
        self.cnt += 1

        
        return self.pred
            

        
        
        #else:
        #    return self.action_buffer
        
