# data_train.py
import re
# from resVAE.resvae import resVAE
# import resVAE.utils as cutils
# from resVAE.config import config
# import resVAE.reporting as report
import torchvision
import torch
# from fastai.basic_data import DataBunch
# from fastai.basic_train import Learner
# from fastai.layers import *
# from fastai.metrics import accuracy
# from fastai.train import ShowGraph

from MeiNN.MeiNN import MeiNN, gene_to_residue_or_pathway_info
# from MeiNN.MeiNN_pytorch import MeiNN_pytorch
from MeiNN.config import config
import os
import json
import numpy as np
import pandas as pd
import csv  # 调用数据保存文件
import pickle
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.linear_model import LogisticRegression
from sklearn.linear_model import Lasso
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
# import TabularAutoEncoder
# import VAE
# import tensorflow.compat.v1 as tf
# tf.disable_v2_behavior()
import tensorflow as tf
# tf.compat.v1.disable_eager_execution()#newly-added-3-27

import torch
from torch import nn
# import torchvision
from torch.autograd import Variable
# import AutoEncoder
import math
import warnings
import AutoEncoder as AE

from time import time

# import tensorflow.keras as keras

from keras import layers

# from keras import objectives
from keras import losses
from keras import regularizers
from keras import backend as K
from keras.models import Model  # 泛型模型
from keras.layers import Dense, Input
from keras.models import load_model

from tensorboardX import SummaryWriter
import tools
import min_norm_solvers

from torch.utils.data import Dataset
import random
#from methods.weight_methods import WeightMethods

import re
import umap
import matplotlib.pyplot as plt
from losses import SupConLoss

logger = SummaryWriter(log_dir="tensorboard_log/")

warnings.filterwarnings("ignore")
CLASSIFIER_FACTOR=10000
CONTRASTIVE_FACTOR=50000
REGULARIZATION_FACTOR=0.0001
TO_PIN_MEMORY=False #True
REG_SIGN="^"
MULTI_TASK_SIGN="~"
SINGLE_TASK_UPPER_BOUND_WEIGHT=0.1
evaluate_weight_site_pathway_step=100
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

def extract_value_between_signs(input_string, sign="$"):
    if sign == ".":
        pattern = r"\.(\d+)(?:\.|$)"
    elif sign == "@":
        pattern = fr"{re.escape(sign)}(.*?){re.escape(sign)}"
    else:
        pattern = fr"{re.escape(sign)}(\d+(?:\.\d+)?){re.escape(sign)}"

    match = re.search(pattern, input_string)

    if match:
        if sign == ".":
            num_str = match.group(1)
            num_digits = len(num_str)
            num = int(num_str)
            return num / (10 ** num_digits)
        elif sign == "@":
            return match.group(1)
        else:
            return float(match.group(1)) if "." in match.group(1) else int(match.group(1))
    else:
        return None


def get_condition_value(row):
    for i, value in enumerate(row):
        if value == 1 or value == 0:
            return i * 2 + value

def multi_label_to_one_dim(y_train):
    umap_labels = ["IBD_F", "IBD_T", "MS_F", "MS_T", "Psoriasis_F", "Psoriasis_T", "RA_F", "RA_T", "SLE_F", "SLE_T", "diabetes1_F", "diabetes1_T"]
    new_y_train_df = pd.DataFrame(y_train.T.apply(get_condition_value, axis=1)).T
    print(new_y_train_df)
    #new_y_train_df.columns = ["Condition"]
    new_y_train_df.index.name = "Index"

    return new_y_train_df

def draw_umap(gene_data_train,y_train,num_of_selected_residue,stage_info="original",training_setting_info=""):
    umap_labels = ["IBD_F", "IBD_T", "MS_F", "MS_T", "Psoriasis_F", "Psoriasis_T", "RA_F", "RA_T", "SLE_F", "SLE_T", "diabetes1_F", "diabetes1_T"]
    #from sklearn.datasets import load_digits

    #digits = load_digits()
    print(y_train)
    print(y_train.shape)
    '''
    Ground TruthIBD
    Ground TruthMS
    Ground TruthPsoriasis
    Ground TruthRA 
    Ground TruthSLE 
    Ground Truthdiabetes1
    '''
    '''
    y_train_onehot = pd.get_dummies(y_train.T, columns = ['Ground TruthIBD','Ground TruthMS','Ground TruthPsoriasis','Ground TruthRA',
                                                            'Ground TruthSLE','Ground Truthdiabetes1'], drop_first=True)
    print(y_train_onehot )
    conditions = ['IBD', 'MS', 'Psoriasis', 'RA', 'SLE', 'diabetes1']
    y_train_columns_list = y_train.T.columns.tolist()
    merged_y_train = {f'{condition}_{i + 1}': y_train.T.loc[:, 'Ground Truth'+condition].iloc[i] for i in range(len(y_train_columns_list)) for condition in conditions}
    new_merged_y_train = pd.DataFrame(merged_y_train, index=[0])
    print(new_merged_y_train)

    y_train_onehot=y_train_onehot.replace([1,0],[True,False])
    print(y_train_onehot )'''


    # Apply the function to the DataFrame and store the results in a new DataFrame with a single row
    new_y_train_df = pd.DataFrame(y_train.T.apply(get_condition_value, axis=1)).T
    print(new_y_train_df)
    #new_y_train_df.columns = ["Condition"]
    new_y_train_df.index.name = "Index"

    print(new_y_train_df)
    #for n_neighbours in (2, 5, 10, 20, 50, 100, 200):
    umap_embedding = umap.UMAP(random_state=42).fit_transform(gene_data_train.T,new_y_train_df.T)#,y_train_onehot)#dataset.cpu())#gene_data_train.T)
    #umap_embedding_2 = umap.UMAP(random_state=42).fit_transform(gene_data_train.T)
    ###
    from sklearn.cluster import KMeans
    if "original" in stage_info:
        kmeans = KMeans(n_clusters=12, random_state=0).fit(umap_embedding)
        kmeans_fit_predict=KMeans(n_clusters=12, random_state=0).fit_predict(umap_embedding,y_train)
    ####
    plt.clf() # clear figure
    plt.cla() # clear axis
    plt.close() # close window
        # Prepare the legend labels and colors
    
    # Create a scatter plot of the UMAP embeddings
    '''
    plt.scatter(umap_embedding[:, 0], umap_embedding[:, 1],c=new_y_train_df.T, cmap='Spectral', s=5,label=umap_labels)
    plt.gca().set_aspect('equal', 'datalim')'''
    #plt.colorbar(boundaries=np.arange(11)-0.5).set_ticks(["IBD_F","IBD_T","MS_F","MS_T","Psoriasis_F","Psoriasis_T","RA_F","RA_T","SLE_F","SLE_T","diabetes1_F","diabetes1_T"])#np.arange(10)
    colors = plt.cm.Spectral(np.linspace(0, 1, len(umap_labels)))

    # Create the scatter plot
    for label, color in zip(range(1, 13), colors):
        indices = (new_y_train_df.T == label).values.ravel()
        plt.scatter(umap_embedding[indices, 0], umap_embedding[indices, 1], c=[color], cmap='Spectral', s=5, label=umap_labels[label - 1])

    plt.gca().set_aspect('equal', 'datalim')
    
    # Add the legend
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize='small')
    
    plt.title('UMAP projection of the gene_data_train dataset '+stage_info+' (num of site='+str(num_of_selected_residue)+')', fontsize=12)

    # Save the plot as a PNG image
    umap_dir_path = "./umap/"

    if not os.path.exists(umap_dir_path):
        os.makedirs(umap_dir_path)
        print("Directory", umap_dir_path, "created.")
    else:
        print("Directory", umap_dir_path, "already exists.")
    output_image_path = umap_dir_path+stage_info+"-site-"+str(num_of_selected_residue)+"-"+training_setting_info+"-umap.png" #"original
    plt.savefig(output_image_path, dpi=300, bbox_inches='tight')

    # Display the plot in the notebook (optional)
    #plt.show()
    if "original" in stage_info:
        return kmeans,kmeans_fit_predict
    else:
        return
    
class CustomDataset(Dataset):
    def __init__(self, data,label,toDebug=False):
        self.label = label
        self.data = data
        self.toDebug=toDebug

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        #img_path = os.path.join(self.img_dir, self.img_labels.iloc[idx, 0])
        #image = read_image(img_path)
        label = self.label[idx, :]
        data = self.data[idx,:]
        if self.toDebug:
            print("DEBUG: inside dataset:")
            print("label")
            print(label)
            print("data")
            print(data)
        return data, label
    

def mkdir(path):
    import os
    # remove first blank space
    path = path.strip()
    # remove \ at the end
    path = path.rstrip("\\")
    # judge whether directory exists
    # exist     True
    # not exist   False
    isExists = os.path.exists(path)
    # judge the result
    if not isExists:
        # if not exist, then create directory
        os.makedirs(path)
        print(path + " directory created successfully.")
        return True
    else:
        # if directory exists, don't create and print it already exists
        #print(path + " directory already exists.")
        return False


def origin_data(data):
    return data


def square_data(data):
    return data ** 2


def log_data(data):
    return np.log(data + 1e-5)


def radical_data(data):
    return data ** (1 / 2)


def cube_data(data):
    return data ** 3


toPrintInfo=False
global_iter_num =0
def return_reg_loss(ae,skip_connection_mode="^dec"):
    reg_loss = 0
    reg_mode_list=skip_connection_mode.split(REG_SIGN)
    if len(reg_mode_list)>=2:
        reg_mode=reg_mode_list[1]
    else:
        reg_mode=""
    
    if reg_mode=="all":
        for i, param in enumerate(ae.parameters()):
            if toPrintInfo:
                print("%d-th layer:" % i)
                # print(name)
                print("param:")
                print(param.shape)
            reg_loss += torch.sum(torch.abs(param))
    elif reg_mode=="dec":
        for i, param in enumerate(ae.decoder1.parameters()):
            if toPrintInfo:
                print("%d-th layer:" % i)
                # print(name)
                print("param:")
                print(param.shape)
            reg_loss += torch.sum(torch.abs(param))
        for i, param in enumerate(ae.decoder2.parameters()):
            if toPrintInfo:
                print("%d-th layer:" % i)
                # print(name)
                print("param:")
                print(param.shape)
            reg_loss += torch.sum(torch.abs(param))
    elif reg_mode=="sftde":
        for i, param in enumerate(ae.decoder1.parameters()):
            if toPrintInfo:
                print("%d-th layer:" % i)
                # print(name)
                print("param:")
                print(param.shape)
            reg_loss += torch.sum(torch.abs(param))
        for i, param in enumerate(ae.decoder2.parameters()):
            if toPrintInfo:
                print("%d-th layer:" % i)
                # print(name)
                print("param:")
                print(param.shape)
            reg_loss += torch.sum(torch.abs(param))
    elif reg_mode=="sftall":
        for i, param in enumerate(ae.decoder1.parameters()):
            if toPrintInfo:
                print("%d-th layer:" % i)
                # print(name)
                print("param:")
                print(param.shape)
            reg_loss += torch.sum(torch.abs(param))
        for i, param in enumerate(ae.decoder2.parameters()):
            if toPrintInfo:
                print("%d-th layer:" % i)
                # print(name)
                print("param:")
                print(param.shape)
            reg_loss += torch.sum(torch.abs(param))
    else :#reg_mode=="sftde":
        pass
        ''' 
        for i, param in enumerate(ae.decoder1.parameters()):
            if toPrintInfo:
                print("%d-th layer:" % i)
                # print(name)
                print("param:")
                print(param.shape)
            reg_loss += torch.sum(torch.abs(param))
        for i, param in enumerate(ae.decoder2.parameters()):
            if toPrintInfo:
                print("%d-th layer:" % i)
                # print(name)
                print("param:")
                print(param.shape)
            reg_loss += torch.sum(torch.abs(param))'''
        
    return reg_loss

'''
def matrix_ones_to_val(matrix,to_value,percentage,count,option=""):
    return matrix

def random_mask_matrix_ones(matrix,to_value,percentage,count,option=""):
    return matrix

def evaluate_accuracy_predict_random_mask_matrix_ones(matrix,masked_matrix,true_matrix):
    predict_mask_accuracy=0.0
    return predict_mask_accuracy
'''

import pandas as pd
import numpy as np

def matrix_zeros_to_val(matrix, to_value):
    """
    Replace all the zeros in the matrix to `to_value`.
    
    Args:
    matrix (pd.DataFrame): The input matrix (Pandas DataFrame)
    to_value (int or float): The value to replace zeros with

    Returns:
    pd.DataFrame: The processed matrix with zeros replaced by `to_value`
    """
    return matrix.replace(0, to_value)

def random_mask_matrix_ones_to_val(matrix, to_value, percentage, count, option=""):
    """
    Replace a percentage or a count of ones in the matrix with `to_value`.
    
    Args:
    matrix (pd.DataFrame): The input matrix (Pandas DataFrame)
    to_value (int or float): The value to replace ones with
    percentage (float): Percentage of ones to replace (0 to 1)
    count (int): Number of ones to replace
    option (str): "p" for percentage, "c" for count

    Returns:
    pd.DataFrame: The processed matrix with ones replaced by `to_value`
    list: The list of masked positions (each element is a 2D [x, x] representing row and column)
    """
    masked_matrix = matrix.copy()
    ones_positions = np.argwhere(matrix.to_numpy() == 1)
    masked_positions = []
    
    if option == "p":
        count = int(len(ones_positions) * percentage)

    elif option == "c":
        assert count <= len(ones_positions), "Count must be less or equal to the total number of 1s in the matrix."

    np.random.shuffle(ones_positions)
    for i in range(count):
        masked_positions.append(ones_positions[i].tolist())
        masked_matrix.iat[masked_positions[-1][0], masked_positions[-1][1]] = to_value

    return masked_matrix, masked_positions

def evaluate_accuracy_predict_random_mask_matrix_ones(pred_matrix, true_matrix, masked_matrix, masked_position_list, threshold):
    """
    Evaluate accuracy and other statistics of `pred_matrix` compared to `true_matrix`.
    
    Args:
    pred_matrix (pd.DataFrame): The predicted matrix (Pandas DataFrame)
    true_matrix (pd.DataFrame): The true matrix (Pandas DataFrame)
    masked_matrix (pd.DataFrame): The masked matrix (Pandas DataFrame)
    masked_position_list (list): The list of masked positions
    threshold (float): Threshold value for comparison

    Returns:
    list: learned_percentile_list
    float: Average of learned_percentile_list
    np.ndarray: Distribution of all the weights of pred_matrix
    np.ndarray: Distribution of elements of pred_matrix which are on the position of 1s in true_matrix
    np.ndarray: Distribution of elements of pred_matrix which are on the position of 0s of true_matrix
    np.ndarray: Distribution of elements of pred_matrix which are on the position of masked_position_list
    """
    learned_percentile_list = []
    for position in masked_position_list:
        row, col = position
        if pred_matrix.iat[row, col] >= threshold:
            learned_percentile_list.append(1)
        else:
            learned_percentile_list.append(0)

    average_learned_percentile = np.mean(learned_percentile_list)

    all_weights = pred_matrix.values.flatten()
    one_positions = np.argwhere(true_matrix.to_numpy() == 1)
    zero_positions = np.argwhere(true_matrix.to_numpy() == 0)

    ones_distribution = np.array([pred_matrix.iat[row, col] for row, col in one_positions])
    zeros_distribution = np.array([pred_matrix.iat[row, col] for row, col in zero_positions])
    masked_distribution = np.array([pred_matrix.iat[row, col] for row, col in masked_position_list])

    return (learned_percentile_list, 
        average_learned_percentile, 
        all_weights, 
        ones_distribution, 
        zeros_distribution, 
        masked_distribution)

   


def assign_multi_task_weight(model,datasetNameList,y_pred_list,y_masked_splited,mask_splited,criterion,log_info,validation_info,single_task_accu_upper_bound_list=[0.93,0.73,0.80,0.94,0.79,0.98],sample_size_list=[53,88,79,49,160,118],multi_task_training_policy="~uniform",skip_connection_mode=""):
    y_pred_masked_list = []  # [y_pred_list[:,0]*len(datasetNameList)]
    loss_list = []  # [y_pred_list[:,0]*len(datasetNameList)]
    pred_loss_total_splited_sum = 0
    loss_single_classifier = 0
    loss_sum=0
    if "#" in skip_connection_mode:
        contrastive_criterion=SupConLoss()
    for i in range(len(datasetNameList)):
        y_pred_masked_list.append(y_pred_list[i].to(device).T * (mask_splited[i].to(device).squeeze()).squeeze())
        current_loss=criterion(y_pred_masked_list[i].T.squeeze(), y_masked_splited[i].to(device).squeeze())
        loss_list.append(current_loss)
        loss_sum+=current_loss
    ####################################################################
    [accuracy, split_accuracy_list]=validation_info
    # After "~" is the multi-task assignment:
    #               "~uni"
    #               "~ran"
    #               "~re-val"
    #               "pwre-val"
    #               "re-ss"
    #               "norm"
    #               "s-gdnm"simple gradnorm
    #               "DRO"
    assign_weight_policy_list=multi_task_training_policy.split(MULTI_TASK_SIGN)
    if len(assign_weight_policy_list)>=2:
        assign_weight_policy=assign_weight_policy_list[1]
    else:
        assign_weight_policy=""

    assign_weight_value_list=len(datasetNameList)*[1.0]
    if assign_weight_policy=="uni":
        assign_weight_value_list=[1.0 for i in range(len(datasetNameList))]
    elif assign_weight_policy=="ran": #TODO:random
        assign_weight_value_list=[random.random() for i in range(len(datasetNameList))]
    elif assign_weight_policy=="re-val": #TODO:reversed porportional to validation accu
        assign_weight_value_list=[1.0-split_accuracy_list[i] for i in range(len(datasetNameList))]
    elif assign_weight_policy=="pwre-val": #TODO:piece-wise reversed validation accu
        #assign_weight_value_list=[]
        for i in range(len(datasetNameList)):
            w=SINGLE_TASK_UPPER_BOUND_WEIGHT
            s=single_task_accu_upper_bound_list[i]
            x=split_accuracy_list[i]
            if x<=s:
                assign_weight_value_list[i]=(w-1)/s*x+1
            else:
                assign_weight_value_list[i]=-w/(s-1)*x+w/(1-s)
    elif assign_weight_policy=="re-ss": #TODO:reverse porportional to task sample size
        assign_weight_value_list=[1.0/sample_size_list[i] for i in range(len(datasetNameList))]
    elif assign_weight_policy=="norm": #TODO:normalize the scale of each task #TODO:gradnorm
        for i in range(len(datasetNameList)): #TODO:make sure,model.encoder4, it's last shared layer
            assign_weight_value_list[i]=1.0/torch.norm(torch.autograd.grad(loss_list[i], model.encoder4.parameters() , retain_graph=True, create_graph=True)[0])
    elif assign_weight_policy=="s-gdnm": #TODO:simple gradnorm ,fix whether has bug
        for i in range(len(datasetNameList)): #TODO:make sure,model.encoder4, it's last shared layer
            assign_weight_value_list[i]=torch.norm(torch.autograd.grad(loss_list[i], model.encoder4.parameters() , retain_graph=True, create_graph=True)[0])
    elif assign_weight_policy=="DRO": #TODO:DRO-like, higher loss, higher weight
        assign_weight_value_list=[loss_list[i]/loss_sum for i in range(len(datasetNameList))]
    elif assign_weight_policy=="L2":
        assign_weight_value_list=loss_list[i]
    else :#uniform
        assign_weight_value_list=[1.0 for i in range(len(datasetNameList))]
    #####################################################
    
    for i in range(len(datasetNameList)):
        temp_single_task_loss = criterion(y_pred_masked_list[i].to(device).T.squeeze(),
                                                             y_masked_splited[i].to(device).squeeze())
        pred_loss_total_splited_sum += assign_weight_value_list[i]*temp_single_task_loss
        logger.add_scalar(log_info+"%d-th task %s loss" % (i, datasetNameList[i]),
                                      temp_single_task_loss, global_step=global_iter_num)
        logger.add_scalar(log_info+"%d-th weight*task %s loss" % (i, datasetNameList[i]),
                                      assign_weight_value_list[i]*temp_single_task_loss, global_step=global_iter_num)
    return y_pred_masked_list,loss_list,pred_loss_total_splited_sum


def single_train_process(num_epochs,data_loader,datasetNameList,ae,gene_data_train_Tensor,toMask,y_train_T_tensor,criterion,
                         path,date,pth_name,toDebug,global_iter_num,log_stage_name,code,toValidate,gene_data_valid_Tensor,valid_label,
                         multi_task_training_policy,learning_rate_list,skip_connection_mode,umap_draw_step,num_of_selected_residue,y_train,mask_option,my_gene_to_residue_info):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    loss_list = []
    for epoch in range(num_epochs):
        for i_data_batch, (images,y_train_T_tensor) in enumerate(data_loader):  # for i, (images, _) in enumerate(data_loader):
            # flatten the image
            images = AE.to_var(images.view(images.size(0), -1))
            images = images.float()
            # forward
            if len(datasetNameList) == 6:
                out, y_pred_list, embedding = ae(images)#gene_data_train_Tensor.T)#partial batch
                if toValidate:
                    valid_out, valid_y_pred_list, valid_embedding = ae(gene_data_valid_Tensor.T)#for validation
            #umap
            if "umapet" in skip_connection_mode and (epoch+1)%umap_draw_step ==0:
                print("embedding.shape")
                print(embedding.shape)
                draw_umap(embedding.T.cpu().detach().numpy(),y_train,num_of_selected_residue,stage_info="3ndstage-train-epo-"+str(epoch),training_setting_info=date)
            ##
            if mask_option is not None and (epoch+1)%evaluate_weight_site_pathway_step ==0:
                my_gene_to_residue_info.evaluate_weight_site_pathway(ae,date+"3rd-epo"+str(epoch))
            #to GPU
            #y_pred_list=y_pred_list.to(device)
            #valid_y_pred_list=valid_y_pred_list.to(device)
            if toMask:
                mask = y_train_T_tensor.ne(0.5)
                y_masked = y_train_T_tensor * mask
                if toDebug:
                    print("DEBUG:y_train_T_tensor is:")
                    print(y_train_T_tensor.shape)
                    print("DEBUG: mask is:")
                    print(mask.shape)
                    print("DEBUG: y_masked is:")
                    print(y_masked.shape)
                y_masked_splited = torch.split(y_masked, 1, 1)
                mask_splited = torch.split(mask, 1, 1)
                if toDebug:
                    print("len of y_masked_splited%d" % len(y_masked_splited))
                    print("DEBUG: y_masked_splited is:")
                    print(y_masked_splited[0].shape)
                    print("DEBUG: mask_splited is:")
                    print("len of mask_splited%d" % len(mask_splited))
                    print(mask_splited[0].shape)
                #################################
                '''
                y_pred_masked_list = []  # [y_pred_list[:,0]*len(datasetNameList)]
                loss_list = []  # [y_pred_list[:,0]*len(datasetNameList)]
                pred_loss_total_splited_sum = 0
                loss_single_classifier = 0
                
                for i in range(len(datasetNameList)):
                    y_pred_masked_list.append(y_pred_list[i].to(device).T * (mask_splited[i].to(device).squeeze()).squeeze())
                    loss_list.append(criterion(y_pred_masked_list[i].T.squeeze(), y_masked_splited[i].to(device).squeeze()))
                    pred_loss_total_splited_sum += criterion(y_pred_masked_list[i].to(device).T.squeeze(),
                                                             y_masked_splited[i].to(device).squeeze())
                    logger.add_scalar(date+code+" "+log_stage_name+": %d-th single dataset %s loss" % (i, datasetNameList[i]),
                                      criterion(y_pred_masked_list[i].to(device).T.squeeze(),
                                                y_masked_splited[i].to(device).squeeze()), global_step=global_iter_num)
                '''#commented 2023-4-23 for different multi-task weight assignment
                if 'accuracy' not in locals().keys():
                    accuracy=0.0
                if 'split_accuracy_list' not in locals().keys():
                    split_accuracy_list=[0.0 for i in range(len(datasetNameList))]             
                y_pred_masked_list,loss_list,pred_loss_total_splited_sum=assign_multi_task_weight(ae,datasetNameList,y_pred_list,y_masked_splited,mask_splited,criterion,(date+code+" "+log_stage_name),[accuracy, split_accuracy_list],
                                         multi_task_training_policy=multi_task_training_policy,skip_connection_mode=skip_connection_mode)
                ##################################
            reg_loss = return_reg_loss(ae,skip_connection_mode)
            loss_single_classifier = pred_loss_total_splited_sum * 100000 + reg_loss * 0.0001 #TODO:add autoencoder reconstruction loss
            
            if "#" in skip_connection_mode:
                contrastive_criterion=SupConLoss()
                loss_single_classifier+= contrastive_criterion(embedding)*CONTRASTIVE_FACTOR
            if "VAE" in skip_connection_mode:
                loss_single_classifier +=ae.kl_divergence
            print(pth_name+" loss: %f" % loss_single_classifier.item())
            optimizer = torch.optim.Adam(filter(lambda p: p.requires_grad, ae.parameters()), lr=learning_rate_list[2])#1e-3
            if "ROnP" in multi_task_training_policy:
                scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'max',factor=0.9,patience=40) # added 23-1-2 for special training policy
            optimizer.zero_grad()
            loss_single_classifier.backward(retain_graph=True)
            # loss_single_classifier_loss_list[dataset_id].append(loss_single_classifier.item())
            optimizer.step()

            global_iter_num = epoch * len(
                data_loader) + i_data_batch + 1  # calculate it's which step start from training
            
            if "*" in skip_connection_mode:
                ae.save_site_gene_pathway_weight_visualization(info=log_stage_name+" epoch "+str(global_iter_num))
            if toValidate:
                normalized_pred_out, num_wrong_pred, accuracy, split_accuracy_list ,auroc_list= tools.evaluate_accuracy_list(
                    datasetNameList, valid_label, valid_y_pred_list,toPrint=False)  # added for validation data#2023-1-8
                if "ROnP" in multi_task_training_policy:
                    scheduler.step(accuracy)
                logger.add_scalar(date + code + " " + log_stage_name + ": total validation accuracy",
                                  accuracy, global_step=global_iter_num)
                for i in range(len(datasetNameList)):# added for validation data#2023-1-8
                    logger.add_scalar(date + code + " " + log_stage_name + ": %d-th single dataset %s validation accuracy"%(i, datasetNameList[i]),
                                      split_accuracy_list[i], global_step=global_iter_num)
            logger.add_scalar(date+code+" "+log_stage_name+": autoencoder reconstruction loss", criterion(out, images), global_step=global_iter_num)
            logger.add_scalar(date+code+" "+log_stage_name+": regularization loss", reg_loss, global_step=global_iter_num)
            logger.add_scalar(date+code+" "+log_stage_name+": classifier predction loss", pred_loss_total_splited_sum, global_step=global_iter_num)
            logger.add_scalar(date+code+" "+log_stage_name+": total train loss", loss_single_classifier.item(), global_step=global_iter_num)
            for name, param in ae.named_parameters():
                logger.add_histogram(date+code+" "+log_stage_name+": "+name, param.data.cpu().numpy(), global_step=global_iter_num)
    torch.save(ae, path + date + pth_name+".pth")#"single-classifier-trained.pth"

    if "MGDA" in multi_task_training_policy:
        torch.save(ae, path + date + pth_name + "1.pth")
        loss_now=0
        grads = {}#[None]*len(datasetNameList)
        scale = [0.0]*len(datasetNameList)
        optimizer = torch.optim.Adam(filter(lambda p: p.requires_grad, ae.parameters()),
                                     lr=learning_rate_list[2])  # 1e-3
        for epoch in range(num_epochs,num_epochs*2):
            for i_data_batch, (images,y_train_T_tensor) in enumerate(data_loader):  # for i, (images, _) in enumerate(data_loader):
                # flatten the image
                images = AE.to_var(images.view(images.size(0), -1))
                images = images.float()
                # forward
                if len(datasetNameList) == 6:
                    out, y_pred_list, embedding = ae(gene_data_train_Tensor.T)#partial batch
                    if toValidate:
                        valid_out, valid_y_pred_list, valid_embedding = ae(gene_data_valid_Tensor.T)  # for validation

                if toMask:
                    mask = y_train_T_tensor.ne(0.5)
                    y_masked = y_train_T_tensor * mask
                    if toDebug:
                        print("DEBUG:y_train_T_tensor is:")
                        print(y_train_T_tensor.shape)
                        print("DEBUG: mask is:")
                        print(mask.shape)
                        print("DEBUG: y_masked is:")
                        print(y_masked.shape)
                    y_masked_splited = torch.split(y_masked, 1, 1)
                    mask_splited = torch.split(mask, 1, 1)
                    if toDebug:
                        print("len of y_masked_splited%d" % len(y_masked_splited))
                        print("DEBUG: y_masked_splited is:")
                        print(y_masked_splited[0].shape)
                        print("DEBUG: mask_splited is:")
                        print("len of mask_splited%d" % len(mask_splited))
                        print(mask_splited[0].shape)
                    y_pred_masked_list = []  # [y_pred_list[:,0]*len(datasetNameList)]
                    loss_list = []  # [y_pred_list[:,0]*len(datasetNameList)]
                    pred_loss_total_splited_sum = 0
                    loss_single_classifier = 0

                    single_task_loss=[0]*len(datasetNameList)
                    for i in range(len(datasetNameList)):
                        optimizer.zero_grad()
                        y_pred_masked_list.append(y_pred_list[i].T * (mask_splited[i].squeeze()).squeeze())
                        single_task_loss[i] = criterion(y_pred_masked_list[i].T.squeeze(),
                                                        y_masked_splited[i].squeeze())
                        loss_list.append(single_task_loss[i])
                        pred_loss_total_splited_sum += single_task_loss[i]#this is loss for single task

                        loss_now=single_task_loss[i]
                        loss_now.backward(retain_graph=True)
                        logger.add_scalar(date + code + " " + log_stage_name + ": %d-th single dataset %s loss" % (
                        i, datasetNameList[i]),single_task_loss[i], global_step=global_iter_num)

                        grads[i] = []
                        if "unet" in skip_connection_mode:
                            for param in ae.encoder1.parameters():
                                if param.grad is not None:
                                    grads[i].append(Variable(param.grad.data.clone(),
                                                             requires_grad=False))  # mask pretrained model weight
                            for param in ae.encoder2.parameters():
                                if param.grad is not None:
                                    grads[i].append(Variable(param.grad.data.clone(),
                                                             requires_grad=False))  # mask pretrained model weight
                            for param in ae.encoder3.parameters():
                                if param.grad is not None:
                                    grads[i].append(Variable(param.grad.data.clone(),
                                                             requires_grad=False))  # mask pretrained model weight
                            for param in ae.encoder4.parameters():
                                if param.grad is not None:
                                    grads[i].append(Variable(param.grad.data.clone(),
                                                             requires_grad=False))  # mask pretrained model weight
                        else:#no "unet" type skip connection, architecture is a whole en/decoder
                            for param in ae.encoder.parameters():
                                if param.grad is not None:
                                    grads[i].append(Variable(param.grad.data.clone(),
                                                             requires_grad=False))  # mask pretrained model weight

                print(grads)
                # Frank-Wolfe iteration to compute scales. 利用FW算法计算loss的scale
                sol, min_norm = min_norm_solvers.MinNormSolver.find_min_norm_element([grads[i] for i in range(len(datasetNameList))])
                for i, t in enumerate(datasetNameList):
                    scale[i] = float(sol[i])

                # Scaled back-propagation  按计算的scale缩放loss并反向传播
                optimizer.zero_grad()
                #rep, _ = model['rep'](images, mask)
                if len(datasetNameList) == 6:
                    out, y_pred_list, embedding = ae(images)#gene_data_train_Tensor.T)#partial batch
                    if toValidate:
                        valid_out, valid_y_pred_list, valid_embedding = ae(gene_data_valid_Tensor.T)  # for validation

                y_pred_masked_list=[]*len(datasetNameList)
                single_task_loss=[]*len(datasetNameList)
                for i, t in enumerate(datasetNameList):
                    #out_t, _ = model[t](rep, masks[t])
                    #loss_t = loss_fn[t](out_t, labels[t])
                    #loss_data[t] = loss_t.data[0]
                    if toMask:
                        mask = y_train_T_tensor.ne(0.5)
                        y_masked = y_train_T_tensor * mask
                        y_masked_splited = torch.split(y_masked, 1, 1)
                        mask_splited = torch.split(mask, 1, 1)
                        y_pred_masked_list[i]=(y_pred_list[i].T * (mask_splited[i].squeeze()).squeeze())
                        single_task_loss[i] = criterion(y_pred_masked_list[i].T.squeeze(),
                                                        y_masked_splited[i].squeeze())
                        loss_t=single_task_loss[i]
                    if i > 0:
                        loss_now = loss_now + scale[i] * loss_t
                    else:
                        loss_now = scale[i] * loss_t
                
                if "#" in skip_connection_mode:
                    contrastive_criterion=SupConLoss()
                    loss_now+= contrastive_criterion(embedding)*CONTRASTIVE_FACTOR
                loss_now.backward(retain_graph=True)
                optimizer.step()

                reg_loss = return_reg_loss(ae,skip_connection_mode)
                loss_single_classifier = pred_loss_total_splited_sum * 100000 + reg_loss * 0.0001
                print("MGDA"+pth_name + " loss: %f" % loss_now.item())
                #optimizer = torch.optim.Adam(filter(lambda p: p.requires_grad, ae.parameters()),
                #                             lr=learning_rate_list[2])  # 1e-3
                #optimizer.zero_grad()
                #loss_single_classifier.backward(retain_graph=True)
                # loss_single_classifier_loss_list[dataset_id].append(loss_single_classifier.item())
                #optimizer.step()
                global_iter_num = epoch * len(
                    data_loader) + i_data_batch + 1  # calculate it's which step start from training
                
                if "*" in skip_connection_mode:
                    ae.save_site_gene_pathway_weight_visualization(info=log_stage_name+"MGDA epoch "+str(global_iter_num))
                if toValidate:
                    normalized_pred_out, num_wrong_pred, accuracy, split_accuracy_list, auroc_list = tools.evaluate_accuracy_list(
                        datasetNameList, valid_label, valid_y_pred_list,
                        toPrint=False)  # added for validation data#2023-1-8
                    logger.add_scalar("MGDA "+date + code + " " + log_stage_name + ": total validation accuracy",
                                      accuracy, global_step=global_iter_num)
                    for i in range(len(datasetNameList)):  # added for validation data#2023-1-8
                        logger.add_scalar(
                            "MGDA "+date + code + " " + log_stage_name + ": %d-th single dataset %s validation accuracy" % (
                            i, datasetNameList[i]),
                            split_accuracy_list[i], global_step=global_iter_num)
                logger.add_scalar("MGDA "+date + code + " " + log_stage_name + ": autoencoder reconstruction loss",
                                  criterion(out, images), global_step=global_iter_num)
                logger.add_scalar("MGDA "+date + code + " " + log_stage_name + ": regularization loss", reg_loss,
                                  global_step=global_iter_num)
                logger.add_scalar("MGDA "+date + code + " " + log_stage_name + ": classifier predction loss",
                                  loss_now.item(), global_step=global_iter_num)
                logger.add_scalar("MGDA "+date + code + " " + log_stage_name + ": total train loss",
                                  loss_now.item(), global_step=global_iter_num)
                for name, param in ae.named_parameters():
                    logger.add_histogram("MGDA "+date + code + " " + log_stage_name + ": " + name, param.data.numpy(),
                                         global_step=global_iter_num)
        #torch.save(ae, path + date + pth_name + ".pth")  # "single-classifier-trained.pth"
        torch.save(ae, path + date + " MGDA "+pth_name + ".pth")
    
    if "NashMTL" in multi_task_training_policy: #TODO: Apply NashMTL
        torch.save(ae, path + date + pth_name + "1.pth")
        loss_now=0
        grads = {}#[None]*len(datasetNameList)
        scale = [0.0]*len(datasetNameList)
        optimizer = torch.optim.Adam(filter(lambda p: p.requires_grad, ae.parameters()),
                                     lr=learning_rate_list[0])  # 1e-3#lr=learning_rate_list[2]
        for epoch in range(num_epochs,num_epochs*2):
            for i_data_batch, (images,y_train_T_tensor) in enumerate(data_loader):  # for i, (images, _) in enumerate(data_loader):
                # flatten the image
                images = AE.to_var(images.view(images.size(0), -1))
                images = images.float()
                # forward
                if len(datasetNameList) == 6:
                    out, y_pred_list, embedding = ae(images)#gene_data_train_Tensor.T)#partial batch
                    if toValidate:
                        valid_out, valid_y_pred_list, valid_embedding = ae(gene_data_valid_Tensor.T)  # for validation

                if toMask:
                    mask = y_train_T_tensor.ne(0.5)
                    y_masked = y_train_T_tensor * mask
                    if toDebug:
                        print("DEBUG:y_train_T_tensor is:")
                        print(y_train_T_tensor.shape)
                        print("DEBUG: mask is:")
                        print(mask.shape)
                        print("DEBUG: y_masked is:")
                        print(y_masked.shape)
                    y_masked_splited = torch.split(y_masked, 1, 1)
                    mask_splited = torch.split(mask, 1, 1)
                    if toDebug:
                        print("len of y_masked_splited%d" % len(y_masked_splited))
                        print("DEBUG: y_masked_splited is:")
                        print(y_masked_splited[0].shape)
                        print("DEBUG: mask_splited is:")
                        print("len of mask_splited%d" % len(mask_splited))
                        print(mask_splited[0].shape)
                    y_pred_masked_list = []  # [y_pred_list[:,0]*len(datasetNameList)]
                    loss_list = []  # [y_pred_list[:,0]*len(datasetNameList)]
                    pred_loss_total_splited_sum = 0
                    loss_single_classifier = 0
                    single_task_loss=[0]*len(datasetNameList)
                    for i in range(len(datasetNameList)):
                        optimizer.zero_grad()
                        y_pred_masked_list.append(y_pred_list[i].T * (mask_splited[i].squeeze()).squeeze())
                        single_task_loss[i] = criterion(y_pred_masked_list[i].T.squeeze(),
                                                        y_masked_splited[i].squeeze())
                        loss_list.append(single_task_loss[i])
                        pred_loss_total_splited_sum += single_task_loss[i]#this is loss for single task

                        loss_now=single_task_loss[i]
                        loss_now.backward(retain_graph=True)
                        logger.add_scalar(date + code + " " + log_stage_name + ": %d-th single dataset %s loss" % (
                        i, datasetNameList[i]),single_task_loss[i], global_step=global_iter_num)

                        grads[i] = []
                        if "unet" in skip_connection_mode:
                            for param in ae.encoder1.parameters():
                                if param.grad is not None:
                                    grads[i].append(Variable(param.grad.data.clone(),
                                                             requires_grad=False))  # mask pretrained model weight
                            for param in ae.encoder2.parameters():
                                if param.grad is not None:
                                    grads[i].append(Variable(param.grad.data.clone(),
                                                             requires_grad=False))  # mask pretrained model weight
                            for param in ae.encoder3.parameters():
                                if param.grad is not None:
                                    grads[i].append(Variable(param.grad.data.clone(),
                                                             requires_grad=False))  # mask pretrained model weight
                            for param in ae.encoder4.parameters():
                                if param.grad is not None:
                                    grads[i].append(Variable(param.grad.data.clone(),
                                                             requires_grad=False))  # mask pretrained model weight
                        else:#no "unet" type skip connection, architecture is a whole en/decoder
                            for param in ae.encoder.parameters():
                                if param.grad is not None:
                                    grads[i].append(Variable(param.grad.data.clone(),
                                                             requires_grad=False))  # mask pretrained model weight

                print(grads)
                # Frank-Wolfe iteration to compute scales. 利用FW算法计算loss的scale
                sol, min_norm = min_norm_solvers.MinNormSolver.find_min_norm_element([grads[i] for i in range(len(datasetNameList))])
                for i, t in enumerate(datasetNameList):
                    scale[i] = float(sol[i])

                # Scaled back-propagation  按计算的scale缩放loss并反向传播
                optimizer.zero_grad()
                #rep, _ = model['rep'](images, mask)
                if len(datasetNameList) == 6:
                    out, y_pred_list, embedding = ae(images)#gene_data_train_Tensor.T)#partial batch
                    if toValidate:
                        valid_out, valid_y_pred_list, valid_embedding = ae(gene_data_valid_Tensor.T)  # for validation

                y_pred_masked_list=[]*len(datasetNameList)
                single_task_loss=[]*len(datasetNameList)
                for i, t in enumerate(datasetNameList):
                    #out_t, _ = model[t](rep, masks[t])
                    #loss_t = loss_fn[t](out_t, labels[t])
                    #loss_data[t] = loss_t.data[0]
                    if toMask:
                        mask = y_train_T_tensor.ne(0.5)
                        y_masked = y_train_T_tensor * mask
                        y_masked_splited = torch.split(y_masked, 1, 1)
                        mask_splited = torch.split(mask, 1, 1)
                        y_pred_masked_list[i]=(y_pred_list[i].T * (mask_splited[i].squeeze()).squeeze())
                        single_task_loss[i] = criterion(y_pred_masked_list[i].T.squeeze(),
                                                        y_masked_splited[i].squeeze())
                        loss_t=single_task_loss[i]
                    if i > 0:
                        loss_now = loss_now + scale[i] * loss_t
                    else:
                        loss_now = scale[i] * loss_t

                if "#" in skip_connection_mode:
                    contrastive_criterion=SupConLoss()
                    loss_now+= contrastive_criterion(embedding)*CONTRASTIVE_FACTOR
                loss_now.backward(retain_graph=True)
                optimizer.step()

                reg_loss = return_reg_loss(ae,skip_connection_mode)
                loss_single_classifier = pred_loss_total_splited_sum * 100000 + reg_loss * 0.0001
                print("NashMTL "+pth_name + " loss: %f" % loss_now.item())
                #optimizer = torch.optim.Adam(filter(lambda p: p.requires_grad, ae.parameters()),
                #                             lr=learning_rate_list[2])  # 1e-3
                #optimizer.zero_grad()
                #loss_single_classifier.backward(retain_graph=True)
                # loss_single_classifier_loss_list[dataset_id].append(loss_single_classifier.item())
                #optimizer.step()
                global_iter_num = epoch * len(
                    data_loader) + i_data_batch + 1  # calculate it's which step start from 
                if "*" in skip_connection_mode:
                    ae.save_site_gene_pathway_weight_visualization(info=log_stage_name+"NashMTL epoch "+str(global_iter_num))
                if toValidate:
                    normalized_pred_out, num_wrong_pred, accuracy, split_accuracy_list, auroc_list = tools.evaluate_accuracy_list(
                        datasetNameList, valid_label, valid_y_pred_list,
                        toPrint=False)  # added for validation data#2023-1-8
                    logger.add_scalar("NashMTL "+date + code + " " + log_stage_name + ": total validation accuracy",
                                      accuracy, global_step=global_iter_num)
                    for i in range(len(datasetNameList)):  # added for validation data#2023-1-8
                        logger.add_scalar(
                            "NashMTL "+date + code + " " + log_stage_name + ": %d-th single dataset %s validation accuracy" % (
                            i, datasetNameList[i]),
                            split_accuracy_list[i], global_step=global_iter_num)
                logger.add_scalar("NashMTL "+date + code + " " + log_stage_name + ": autoencoder reconstruction loss",
                                  criterion(out, images), global_step=global_iter_num)
                logger.add_scalar("NashMTL "+date + code + " " + log_stage_name + ": regularization loss", reg_loss,
                                  global_step=global_iter_num)
                logger.add_scalar("NashMTL "+date + code + " " + log_stage_name + ": classifier predction loss",
                                  loss_now.item(), global_step=global_iter_num)
                logger.add_scalar("NashMTL "+date + code + " " + log_stage_name + ": total train loss",
                                  loss_now.item(), global_step=global_iter_num)
                for name, param in ae.named_parameters():
                    logger.add_histogram("NashMTL "+date + code + " " + log_stage_name + ": " + name, param.data.numpy(),
                                         global_step=global_iter_num)
        #torch.save(ae, path + date + pth_name + ".pth")  # "single-classifier-trained.pth"
        torch.save(ae, path + date + " NashMTL "+pth_name + ".pth")
    return ae,loss_list,global_iter_num



# Define the single_task_training_one_epoch function
def single_task_training_one_epoch(stageName,datasetNameList,ae, optimizer, criterion, data_loader, task_idx, num_epochs, dataset,batch_size,batch_size_ratio,gene_data_train,path,date,model_dict,model_type,AE_loss_list,gene,count,fixed_x,toValidate,gene_data_valid_Tensor,skip_connection_mode,toPrintInfo=False, toMask=True):
    criterionBCE = nn.BCELoss()
    criterionMSE = nn.MSELoss()
    for epoch in range(num_epochs):
        print("Now epoch:%d"%epoch)
        t0 = time()
        for i_data_batch, [images,y_train_T_tensor] in enumerate(data_loader):  # for i, (images, _) in enumerate(data_loader):
            images = AE.to_var(images.view(images.size(0), -1)).float()
            if toPrintInfo:
                print("DEBUG INFO:before the input of model MeiNN")
                print(images)
            #y_pred_masked = y_pred
            y_masked = y_train_T_tensor
            out, y_pred_list, embedding = ae(images)
            if toValidate:
                valid_out, valid_y_pred_list, valid_embedding = ae(gene_data_valid_Tensor.T)  # for validation
            y_masked = y_train_T_tensor[:, task_idx:task_idx+1]

            if toMask:
                mask = y_masked.ne(0.5)
                # Move mask and y_masked to the same device as y_pred_list[task_idx]
                mask = mask.to(y_pred_list[task_idx].device)
                y_masked = y_masked.to(y_pred_list[task_idx].device)
                y_masked = y_masked * mask

            y_pred_masked = y_pred_list[task_idx] * mask

            reg_loss = return_reg_loss(ae)
            print("="*100)
            print("y_pred_masked")
            print(y_pred_masked)
            print("y_masked")
            print(y_masked)
            print("criterionBCE(y_pred_masked, y_masked)")
            print(criterionBCE(y_pred_masked, y_masked))
            print("="*100)
            if "MSE" in skip_connection_mode:
                criterion_reconstruct=nn.MSELoss()
            else:
                criterion_reconstruct=nn.BCELoss()
            loss = reg_loss * 0.0001  + criterion_reconstruct(out, images) * 1 #criterionBCE(y_pred_masked, y_masked) * 10000
            print("reg_loss%f,ae loss%f,prediction loss%f"
                  % (reg_loss, criterion_reconstruct(out, images), criterionBCE(y_pred_masked, y_masked)))

            print("loss: %f" % loss.item())
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            
            AE_loss_list.append(loss.item())
            if (epoch + 1) % 10 == 0:
                print('Epoch [%d/%d], Iter [%d/%d] Loss: %.4f Time: %.2fs'
                      % (epoch + 1, num_epochs, epoch + 1, len(dataset) // batch_size, loss.item(), time() - t0))
                
        if (epoch + 1) % 10 == 0 and batch_size_ratio==1.0:#batch_size_ratio added
            # save the reconstructed images
            fixed_x = fixed_x.float()
            reconst_images, y_pred, embedding = ae(fixed_x)  # prediction
            reconst_images = reconst_images.view(reconst_images.size(0), gene_data_train.shape[
                0])  # reconst_images = reconst_images.view(reconst_images.size(0), 1, 28, 28)
            # mydir = 'E:/JI/4 SENIOR/2021 fall/VE490/ReGear-gyl/ReGear/test_sample/data/'
            mkpath = ".\\result\\%s" % date
            mkdir(mkpath)
            myfile = 'rcnst_img_bt%d_ep%d.png' % (epoch + 1, (epoch + 1))
            reconst_images_path = os.path.join(mkpath, myfile)
            torchvision.utils.save_image(reconst_images.data.cpu(), reconst_images_path)
        ##################
        model = model_dict[model_type]()
    for i, param in enumerate(ae.parameters()):
        print("%d-th layer:" % i)
        print("param:")
        print(param.shape)
    torch.save({"epoch": num_epochs,  # 一共训练的epoch
                "model_state_dict": ae.state_dict(),  # 保存模型参数×××××这里埋个坑××××
                "optimizer": optimizer.state_dict()}, path + date + '.tar')

    torch.save(ae, path + date + f"stl-{datasetNameList[task_idx]}-{stageName}.pth")  # save the whole autoencoder network
    AE_loss_list_df = pd.DataFrame(AE_loss_list)
    AE_loss_list_df.to_csv(path + date + "_AE_loss_list).csv", sep='\t')
    if count == 1:
        with open(path + date + '_train_model_pytorch.pickle', 'wb') as f:
            pickle.dump((gene, ae), f)  # pickle.dump((gene, model), f)
    else:
        with open(path + date + '_train_model_pytorch.pickle', 'ab') as f:
            pickle.dump((gene, ae), f)  # pickle.dump((gene, model), f)

    return ae,AE_loss_list


# Only train regression model, save parameters to pickle file
def run(path, date, code, X_train, y_train, platform, model_type, data_type, HIDDEN_DIMENSION, toTrainMeiNN,
        toAddGenePathway=False, toAddGeneSite=False, multiDatasetMode='multi-task', datasetNameList=[],
        num_of_selected_residue=1000, lossMode='reg_mean', selectNumPathwayMode='=num_gene',
        num_of_selected_pathway=500, AE_epoch_from_main=1000, NN_epoch_from_main=1000,
        batch_size_mode="ratio", batch_size_ratio=0.1, separatelyTrainAE_NN=True, toMask=True,
        gene_pathway_dir="./dataset/GO term pathway/matrix.csv",
        pathway_name_dir="./dataset/GO term pathway/gene_set.txt",
        gene_name_dir="./dataset/GO term pathway/genes.txt",
        framework='keras',skip_connection_mode="unet",
        toValidate=False,valid_data=None,valid_label=None,multi_task_training_policy="no",learning_rate_list=[1e-3,1e-3,1e-3]):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    #model = model.to(device)
    data_dict = {'origin_data': origin_data, 'square_data': square_data, 'log_data': log_data,
                 'radical_data': radical_data, 'cube_data': cube_data}
    model_dict = {'LinearRegression': LinearRegression, 'LogisticRegression': LogisticRegression,
                  'L1': Lasso, 'L2': Ridge, 'RandomForest': RandomForestRegressor, 'AE': AE.Autoencoder}

    if toAddGenePathway:
        # the following added 22-4-24 for go term pathway
        gene_pathway_csv_data = pd.read_csv(gene_pathway_dir, header=None, dtype='int')  # 防止弹出警告
        pathway_name_data = pd.read_csv(pathway_name_dir,
                                        header=None)  # , dtype='str', sep=',')#, header=0, dtype='str')
        # pathway_name_data_df=pathway_name_data.values.tolist()
        gene_name_data = pd.read_csv(gene_name_dir,
                                     header=None)  # , dtype='str', sep=',')#, header=0, dtype='str', sep=',')
        # gene_name_data_df = gene_name_data.values.tolist()
        gene_pathway_df = pd.DataFrame(gene_pathway_csv_data)  # , columns=gene_name_data, index=pathway_name_data)
        print("INFO: gene_pathway_df=")
        print(gene_pathway_df)
        print("INFO : pathway_name_data")
        print(pathway_name_data)
        print("INFO : gene_name_data")
        print(gene_name_data)
        gene_pathway_df.index = pathway_name_data[0].values.tolist()
        gene_pathway_df.columns = gene_name_data[0].values.tolist()  # .index.values.tolist()
        print("INFO: gene_pathway_df after adding column and index")
        print(gene_pathway_df)
        # print("INFO: gene_pathway_df.index")
        # print(gene_pathway_df.index.values.tolist())
        print("gene_pathway_df.loc['GOBP_MITOCHONDRIAL_GENOME_MAINTENANCE']")
        print(gene_pathway_df.loc['GOBP_MITOCHONDRIAL_GENOME_MAINTENANCE'])
        # genename_to_genepathway_index_map=
        # gene_pathway_df.rename(columns=gene_name_data, index=pathway_name_data)
        # print(gene_pathway_df.head(10))
        # above added 22-4-24 for go term pathway

    with open(platform, 'r') as f:
        gene_dict = json.load(f)
        f.close()

    count = 0
    num = len(gene_dict)
    gene_list = []
    print('Now start training gene...')

    data_train = data_dict[data_type](X_train)
    data_valid = valid_data#data_dict[data_type](valid_data)
    print("data_train:")
    print(data_train)
    # print("gene_dict:")
    # print(gene_dict)
    gene_data_train = []
    gene_data_valid = []
    residuals_name = []
    model = None
    count_gene = 0
    count_residue = 0
    gene_to_id_map = {}
    residue_to_id_map = {}
    gene_present_list = set()
    mode_all_gene_and_residue = False
    global_iter_num=0
    '''
    data_train_df=pd.DataFrame(data_train)
    print("data_train_df=")
    print(data_train_df)
    print("y_train")
    print(y_train)
    if code=="GSE66695":
        data_label_df0=pd.DataFrame(y_train,columns=['Ground Truth'],index=data_train_df.columns)
    else:
        data_label_df0 = pd.DataFrame(y_train,columns=['Ground Truth'])
    data_label_df=data_label_df0.T
    print("data_label_df=")
    print(data_label_df)
    data_train_label_df=data_train_df.append(data_label_df)#pd.concat([data_train_df, data_label_df], axis=0)
    print("after join data and label")
    print(data_train_label_df)
    from scipy import stats
    data_train_label_df_T=data_train_label_df.T
    print("data_train_label_df_T[data_train_label_df_T['Ground Truth']==1.0]")
    print(data_train_label_df_T[data_train_label_df_T['Ground Truth']==1.0])
    t_test_result=stats.ttest_ind(data_train_label_df_T[data_train_label_df_T['Ground Truth']==1.0], data_train_label_df_T[data_train_label_df_T['Ground Truth']==0.0])
    print("t_testresult=")
    print(t_test_result)
    print("t_testresult.pvalue=")
    print(t_test_result.pvalue)
    print("t_testresult.pvalue.shape=")
    print(t_test_result.pvalue.shape)

    data_train_label_df['pvalue']=t_test_result.pvalue
    print("data_train_label_df added pvalue")
    print(data_train_label_df)
    print("t_testresult.pvalue.sort()=")
    print(np.sort(t_test_result.pvalue))
    print("data_train_label_df.sort_values(by='pvalue',ascending=True)")
    data_train_label_df_sorted_by_pvalue=data_train_label_df.sort_values(by='pvalue', ascending=True)
    print(data_train_label_df_sorted_by_pvalue)
    print("data_train_label_df_sorted_by_pvalue.iloc[1:,:-1])")
    data_train_label_df_sorted_by_pvalue_raw=data_train_label_df_sorted_by_pvalue.iloc[1:, :-1]
    print(data_train_label_df_sorted_by_pvalue_raw)

    selected_residue_train_data=data_train_label_df_sorted_by_pvalue_raw.iloc[:num_of_selected_residue,:]
    print("selected_residue_train_data)")
    print(selected_residue_train_data)
    data_train=selected_residue_train_data
    '''
    # data_train_label_df.sort_values(by='pvalue',ascending=True)
    # t_test_result.pvalue.sort()
    toPrintInfo = False
    for (i, gene) in enumerate(gene_dict):
        count += 1
        if toPrintInfo:
            print("%s-th,gene=%s,gene_dict[gene]=%s" % (i, gene, gene_dict[gene]))
        # gene_data_train = []
        # residuals_name = []

        # following added 22-4-14
        if mode_all_gene_and_residue:
            gene_to_id_map[gene] = count_gene
            count_gene += 1
            for residue in gene_dict[gene]:
                # gene_to_residue_map[gene_to_id_map[gene]][residue_to_id_map[residue]] = 1  # added 22-4-14
                residue_to_id_map[residue] = count_residue  # added 22-4-14
                count_residue += 1  # added 22-4-14
        # above added 22-4-14

        for residue in data_train.index:
            if residue in gene_dict[gene]:
                if (residue not in (residuals_name)):  # added 2022-4-14
                    residuals_name.append(residue)
                    gene_data_train.append(data_train.loc[residue])
                    gene_data_valid.append(data_valid.loc[residue])#added 2023-1-8
                # following added 22-4-14
                if not mode_all_gene_and_residue:
                    if gene not in gene_to_id_map:
                        gene_to_id_map[gene] = count_gene
                        count_gene += 1
                        gene_present_list.add(gene)
                        # gene_to_residue_map.append([])
                    if residue not in residue_to_id_map:
                        residue_to_id_map[residue] = count_residue  # added 22-4-14
                        count_residue += 1  # added 22-4-14
                        # gene_to_residue_map.append(1)

        '''for residue in data_valid.index:#added 2023-1-8 for validation data
            if residue in gene_dict[gene]:
                if (residue not in (residuals_name)):  # added 2022-4-14
                    residuals_name.append(residue)
                    gene_data_valid.append(data_valid.loc[residue])'''

                # above added 22-4-14
        if len(gene_data_train) == 0:
            # print('Contained Nan data, has been removed!')
            continue

        # gene_data_train = np.array(gene_data_train)
        if gene not in gene_list:
            gene_list.append(gene)

        if toPrintInfo:
            print('No.' + str(i) + 'Now training ' + gene + "\tusing " + model_type + "\ton " + data_type + "\t" + str(
                int(count * 100 / num)) + '% ...')
        # print("gene_data_train.shape[1]")
        # print(np.array(gene_data_train).shape[1])

        if count == 1:
            with open(path + date + "_" + code + "_train_model.pickle", 'wb') as f:#path + date + "_" + code + "_" + model_type + "_" + data_type + 'train_model.pickle'
                pickle.dump((gene, model), f)
        else:
            with open(path + date + "_" + code + "_train_model.pickle", 'ab') as f:
                pickle.dump((gene, model), f)
        if toPrintInfo:
            print('finish!')

    #############2022-5-21##############

    if toAddGenePathway:
        gene_present_list_df = pd.DataFrame(list(gene_present_list), columns=['name'])
        gene_present_set = set(gene_present_list)
        where_input_gene_is_not_in_go_term_set = gene_present_set.difference(
            set(gene_pathway_df.columns.values.tolist()))
        print("where_input_gene_is_not_in_go_term_set")
        print(where_input_gene_is_not_in_go_term_set)
        gene_pathway_df_with_input_gene = gene_pathway_df.loc[gene_pathway_df.apply(np.sum, axis=1) > 0]
        gene_pathway_df_with_input_gene[list(where_input_gene_is_not_in_go_term_set)] = np.zeros(
            (gene_pathway_df_with_input_gene.shape[0], len(where_input_gene_is_not_in_go_term_set)), dtype=np.int)
        print("gene_pathway_df_with_input_gene")
        print(gene_pathway_df_with_input_gene)
        print("selected present gene from go term:")
        gene_pathway_df_with_only_present_gene = gene_pathway_df_with_input_gene[gene_present_list]
        print(gene_pathway_df_with_only_present_gene)
        gene_pathway_needed = gene_pathway_df_with_only_present_gene.loc[
            gene_pathway_df_with_only_present_gene.apply(np.sum, axis=1) > 0]
        print(" remove rows that are all 0,gene_pathway_needed")
        print(gene_pathway_needed)
        gene_pathway_needed[list(where_input_gene_is_not_in_go_term_set)] = np.ones(
            (gene_pathway_needed.shape[0], len(where_input_gene_is_not_in_go_term_set)), dtype=np.int)
        print(" remove rows that are all 0,gene_pathway_needed,add never exist input gene")
        print(gene_pathway_needed)
        gene_pathway_needed['gene-pathway sum'] = gene_pathway_needed.apply(lambda x: sum(x), axis=1)
        print(" remove rows that are all 0,gene_pathway_needed,add never exist input gene,with connection sum")
        print(gene_pathway_needed)
        gene_pathway_needed.sort_values(by='gene-pathway sum', ascending=False)
        print(" remove rows that are all 0,gene_pathway_needed,add never exist input gene,sorted by connection sum")
        print(gene_pathway_needed)
        if selectNumPathwayMode == '=num_gene':
            selected_pathway_num = gene_pathway_needed.shape[1]
        elif selectNumPathwayMode == 'eq_dif':
            selected_pathway_num = count_gene - (count_residue - count_gene)
        elif selectNumPathwayMode == 'num':
            selected_pathway_num = num_of_selected_pathway
        gene_pathway_needed = gene_pathway_needed.iloc[:selected_pathway_num - 1, :-1]
        print(
            " remove rows that are all 0,gene_pathway_needed,add never exist input gene,sorted by connection sum,finally selected certain pathway:")
        print(gene_pathway_needed)
        gene_pathway_needed_reversed = gene_pathway_needed.replace([1, 0], [0, 1]).values.tolist()
        print("gene_pathway_needed_reversed:")
        print(gene_pathway_needed.replace([1, 0], [0, 1]))
        gene_pathway_needed.to_csv(
            path + date + "_" + code + "_gene_level" + "gene_pathway_needed).csv", sep='\t')
        import seaborn as sns
        import matplotlib.pylab as plt
        heat_map_gene_pathway = sns.heatmap(gene_pathway_needed, linewidth=1, annot=False)
        plt.title(path + date + 'multi-task-MeiNN gene-pathway known info HeatMap')
        plt.savefig(path + date + 'multi-task-MeiNN_gene_pathway_known_info_heatmap.png')
        # plt.show()
    ####################################
    if toAddGenePathway and False:
        gene_present_list_df = pd.DataFrame(list(gene_present_list), columns=['name'])
        temp_list = list(range(len(gene_name_data)))

        # for i, val in enumerate(temp_list):
        #    temp_list[i] = str(val)
        gene_present_index = gene_present_list_df.replace(gene_name_data.values.tolist(), temp_list)
        # gene_present_index_sorted=gene_present_index.sort_values('name')
        gene_present_index_list = gene_present_index.values.tolist()
        print("**********gene_present_index_list********")
        print(gene_present_index_list)
        print(len(gene_present_index_list))
        import re
        # for i, val in enumerate(gene_present_index_list):
        # gene_present_index_list[i] = str(val)
        # re.search(re_exp)
        re_exp = r"[^0-9\]\[]"
        where_input_gene_is_not_in_go_term = [False] * len(gene_present_index_list)
        for i, val in enumerate(gene_present_index_list):
            where_input_gene_is_not_in_go_term[i] = re.match(re_exp, str(val))
        # where_input_gene_is_not_in_go_term = list(filter(lambda x: re.match(re_exp, x) != None, gene_present_index_list))
        # where_input_gene_is_not_in_go_term = gene_present_index_list.str.contains(re_exp)
        print("**********where_input_gene_is_not_in_go_term********")
        print(where_input_gene_is_not_in_go_term)
        print(len(where_input_gene_is_not_in_go_term))
        gene_name_data_list = gene_name_data.values.tolist()
        print("**gene_name_data_list:**")
        print(gene_name_data_list)
        print(gene_name_data_list[0])
        print("**gene_to_id_map:**")
        print(gene_to_id_map)
        # print(gene_to_id_map['ABCDEFG'])
        print("**********in gene to id map but not in go term********")
        count1 = 0
        for gene in gene_present_list:
            if str(gene) not in gene_name_data_list:
                print(gene)
                print(count1)
                count1 += 1
        gene_pathway_present_gene_index = gene_pathway_csv_data.loc[:gene_present_index_list]
    # save the dictionary : following added 22-4-14

    np.save(
        path + date + "_" + code  + "_residue_name_list" + ".txt",
        residuals_name)  # added 5-12
    np.save(
        path + date + "_" + code  + "_gene_to_id_map" + ".txt",
        gene_to_id_map)
    np.save(
        path + date + "_" + code  + "_residue_to_id_map" + ".txt",
        residue_to_id_map)

    print("len residue_to_id_map%d" % len(residue_to_id_map))
    print("len gene_to_id_map%d" % len(gene_to_id_map))
    gene_to_residue_map = [[0 for i in range(len(residue_to_id_map))] for i in range(len(gene_to_id_map))]
    gene_to_residue_map_reversed = [[1 for i in range(len(residue_to_id_map))] for i in range(len(gene_to_id_map))]
    count_connection = 0
    if toAddGeneSite:
        for id in gene_to_id_map:
            if (id in gene_dict):
                for residue in gene_dict[id]:
                    if residue in residue_to_id_map:
                        gene_to_residue_map[gene_to_id_map[str(id)]][residue_to_id_map[residue]] = 1
                        gene_to_residue_map_reversed[gene_to_id_map[str(id)]][residue_to_id_map[residue]] = 0
                        count_connection += 1

    np.save(
        path + date + "_" + code + "_gene_level" + "gene2residue_map)" + ".txt",
        gene_to_residue_map)

    heat_map_gene_residue = sns.heatmap(gene_to_residue_map, linewidth=1, annot=False)
    plt.title(path + date + 'multi-task-MeiNN gene-residue known info HeatMap')
    plt.savefig(path + date + 'multi-task-MeiNN_gene_residue_known_info_heatmap.png')
    # plt.show()
    # above added 22-4-14
    # gene_data_train_Tensor=gene_data_train
    gene_data_train = np.array(gene_data_train)  # added line on 2-3
    gene_data_train_Tensor = torch.from_numpy(gene_data_train).float()
    gene_data_valid = np.array(gene_data_valid)  # added 2023-1-8
    gene_data_valid_Tensor = torch.from_numpy(gene_data_valid).float()# added 2023-1-8
    print("gene_data_train=")
    print(gene_data_train)
    np.save(
        path + date + "_" + code + "gene_data_train)" + ".txt",
        gene_data_train)
    # ae=None
    autoencoder = None
    fcn = None
    ##added for GPU
    
    gene_data_train_Tensor=gene_data_train_Tensor.to(device)
    gene_data_valid_Tensor=gene_data_valid_Tensor.to(device)

    if True or (model_type == "VAE" or model_type == "AE" or model_type == "MeiNN"):
        # encoding_dim = 400
        latent_dim = HIDDEN_DIMENSION
        print("DEBUG INFO:we entered MeiNN code")
        if True or toTrainMeiNN:
            if framework == 'keras':
                print("DEBUG INFO:we entered to train MeiNN keras code")
                gene_data_train = np.load(path + date + "_" + code + "gene_data_train)" + ".txt.npy")
                my_gene_to_residue_info = gene_to_residue_or_pathway_info(gene_to_id_map, residue_to_id_map,
                                                                          gene_to_residue_map,
                                                                          count_connection,
                                                                          gene_to_residue_map_reversed,
                                                                          gene_pathway_needed,
                                                                          gene_pathway_needed_reversed)
                myMeiNN = MeiNN(config, path, date, code, gene_data_train.T, y_train.T, platform, model_type, data_type,
                                HIDDEN_DIMENSION, toTrainMeiNN, AE_epoch_from_main=AE_epoch_from_main,
                                NN_epoch_from_main=NN_epoch_from_main, separatelyTrainAE_NN=separatelyTrainAE_NN,
                                model_dir='./results/models',
                                gene_to_residue_or_pathway_info=my_gene_to_residue_info, toAddGeneSite=toAddGeneSite,
                                toAddGenePathway=toAddGenePathway,
                                multiDatasetMode=multiDatasetMode, datasetNameList=datasetNameList, lossMode=lossMode,skip_connection_mode=skip_connection_mode)

                # myMeiNN.build()
                myMeiNN.compile()
                # myMeiNN.fcn.fit(gene_data_train.T, y_train.T, epochs=NN_epoch_from_main, batch_size=79, shuffle=True)
                myMeiNN.fit()
            elif framework == 'pytorch':
                myMeiNN = None
                print("DEBUG INFO:we entered to train MeiNN pytorch code")
                gene_data_train = np.load(path + date + "_" + code + "gene_data_train)" + ".txt.npy")

                ############if have random mask on site-gene-pathway evaluation#############
                # "$20$" means mask 20% of the network site-gene-pathway connection
                # ".50", or ".xx" means , it will make the connection not defined by site-gene-pathway, mask 0.5(or other values) but not originally hard 0 
                umap_draw_step=extract_value_between_signs(skip_connection_mode,"+")
                soft_mask_to_value=extract_value_between_signs(skip_connection_mode,".")
                mask_option=extract_value_between_signs(skip_connection_mode,"@")
                mask_percentage=float(extract_value_between_signs(skip_connection_mode,"$"))/100.0
                if umap_draw_step is not None:
                    print("umap_draw_step = " + str(umap_draw_step))
                if soft_mask_to_value is not None:
                    print("soft_mask_to_value = " + str(soft_mask_to_value))
                if mask_option is not None:
                    print("mask_option = " + str(mask_option))
                if mask_percentage is not None:
                    print("mask_percentage ="+str(mask_percentage))
                ###################################################################
                my_gene_to_residue_info = gene_to_residue_or_pathway_info(gene_to_id_map, residue_to_id_map,
                                                                          gene_to_residue_map,
                                                                          count_connection,
                                                                          gene_to_residue_map_reversed,
                                                                          gene_pathway_needed,
                                                                          gene_pathway_needed_reversed)
                ##############random mask evaluation###############################
                if mask_option is not None:
                    print( my_gene_to_residue_info.gene_pathway)
                    print( my_gene_to_residue_info.gene_to_residue_map)
                    my_gene_to_residue_info.soften(soft_mask_to_value,part_option="all")
                    print("my_gene_to_residue_info softened")
                    print( my_gene_to_residue_info.gene_pathway)
                    print( my_gene_to_residue_info.gene_to_residue_map)
                    my_gene_to_residue_info.mask_info(soft_mask_to_value, mask_percentage, mask_percentage,option=mask_option,part_option="all")
                    print("my_gene_to_residue_info site-gene-pathway prior random masked")
                    print( my_gene_to_residue_info.gene_pathway)
                    print( my_gene_to_residue_info.gene_to_residue_map)
                    #return ae,list()
                ##########added from train_pytorch.py############
                num_epochs = AE_epoch_from_main
                if batch_size_mode == "ratio":
                    batch_size = int(gene_data_train.shape[1] * batch_size_ratio)#originally int()  # gene_data_train.shape[0]#100#809
                else:
                    batch_size = int(gene_data_train.shape[1])
                # hidden_size = 10
                dataset = CustomDataset(gene_data_train_Tensor.T,torch.from_numpy(y_train.T.values).float())# y is added for alignment partial batch # .flatten()#gene_data_train.view(gene_data_train.size[0], -1)
                # dataset = gene_data_train  # dsets.MNIST(root='../data',

                # train=True,
                # transform=transforms.ToTensor(),
                # download=True)
                data_loader = torch.utils.data.DataLoader(dataset=dataset,
                                                          batch_size=batch_size,
                                                          shuffle=True,
                                                          pin_memory=TO_PIN_MEMORY)
                print("gene_data_train.shape")
                print(gene_data_train.shape)
                print("dataset.shape")
                print(len(dataset))
                ###model defined#
                ae = AE.MeiNN(config, path, date, code, gene_data_train.T, y_train.T, platform, model_type, data_type,
                              HIDDEN_DIMENSION, toTrainMeiNN, AE_epoch_from_main=AE_epoch_from_main,
                              NN_epoch_from_main=NN_epoch_from_main, separatelyTrainAE_NN=separatelyTrainAE_NN,
                              model_dir='./results/models',
                              gene_to_residue_or_pathway_info=my_gene_to_residue_info, toAddGeneSite=toAddGeneSite,
                              toAddGenePathway=toAddGenePathway,
                              multiDatasetMode=multiDatasetMode, datasetNameList=datasetNameList, lossMode=lossMode,
                              skip_connection_mode=skip_connection_mode)#addedd skip connection mode

                if "umapo" in skip_connection_mode or "umapet" in skip_connection_mode:
                    kmeans,kmeans_fit_predict=draw_umap(gene_data_train,y_train,num_of_selected_residue,stage_info="original",training_setting_info=date)
                    toKmeans=False
                    if toKmeans:
                        umap_fit_valid=umap.UMAP(random_state=42).fit_transform(valid_data)
                        kmeans_valid=kmeans.predict(umap_fit_valid)
                        print(kmeans_valid)
                        print(valid_label)
                        valid_label_one_dim=multi_label_to_one_dim(valid_label)
                        kmeans_valid_df=pd.DataFrame(kmeans_valid)
                        valid_label_df=pd.DataFrame(valid_label)
                        valid_label_one_dim_df=pd.DataFrame(valid_label_one_dim)
                        kmeans_valid_df.to_csv("4-26validlabelkmeans.csv")
                        valid_label_df.to_csv("4-26validlabel.csv")
                        valid_label_one_dim_df.to_csv("4-26validlabel-onedim.csv")
                        #print(kmeans_fit_predict.predict(umap_fit_valid))
                        #print(valid_label)
                    if "umapo" in skip_connection_mode:
                        return ae,list()
                # ae = AE.Autoencoder(in_dim=gene_data_train.shape[0],
                #                    h_dim=HIDDEN_DIMENSION)  # in_dim=gene_data_train.shape[1]

                if torch.cuda.is_available():
                    ae.cuda()
                ##for GPU
                ae=ae.to(device)
                gene_data_train_Tensor=gene_data_train_Tensor.to(device)
                gene_data_valid_Tensor=gene_data_valid_Tensor.to(device)
                criterion = nn.BCELoss()
                optimizer = torch.optim.Adam(ae.parameters(), lr=learning_rate_list[0])#0.001
                scheduler = None
                if "ROnP" in multi_task_training_policy:
                    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'max',factor=0.9,patience=40)
                iter_per_epoch = len(data_loader)
                if batch_size_ratio==1.0:
                    data_iter = iter(data_loader)

                    # save fixed inputs for debugging
                    fixed_x = next(data_iter)  # fixed_x, _ = next(data_iter)
                    fixed_x=fixed_x[0]#added to align CustomDataset
                    # mydir = './data/'
                    # difine the directory to be created
                    mkpath = ".\\result\\%s" % date
                    path_flag=0
                    if not mkdir(mkpath) and path_flag==0:
                        print(path + " directory already exists.")
                        path_flag+=1
                    myfile = "t_img_bth%d.png" % (i + 1)
                    images_path = os.path.join(mkpath, myfile)
                    torchvision.utils.save_image(Variable(fixed_x).data.cpu(), images_path)
                    fixed_x = AE.to_var(fixed_x.view(fixed_x.size(0), -1))
                AE_loss_list = []
                y_train_T_tensor = torch.from_numpy(y_train.T.values).float() #TODO: make label in dataset 
                toPrintInfo = True
                
                '''
                class MultiTaskLossWrapper(nn.Module):
                    def __init__(self, task_num):
                        super(MultiTaskLossWrapper, self).__init__()
                        self.task_num = task_num
                        self.log_vars = nn.Parameter(torch.zeros((task_num)))

                    def forward(self, y_preds,y_true):
                        mse, crossEntropy = MSELossFlat(), CrossEntropyFlat()
                        loss_sum=0
                        for i,y_true_i in enumerate(y_true):
                            loss[i]=crossEntropy(y_preds[i], y_true_i)
                            loss_sum+=loss[i]
                        return loss_sum

                def acc_1(y_preds,y_true):
                    return accuracy(y_preds[0],y_true[0])
                def acc_2(y_preds,y_true):
                    return accuracy(y_preds[1],y_true[1])
                def acc_3(y_preds,y_true):
                    return accuracy(y_preds[2],y_true[2])
                def acc_4(y_preds,y_true):
                    return accuracy(y_preds[3],y_true[3])
                def acc_5(y_preds,y_true):
                    return accuracy(y_preds[4],y_true[4])
                def acc_6(y_preds,y_true):
                    return accuracy(y_preds[5],y_true[5])
                '''
                #########22-8-2 fast.ai MTL demo####################
                '''
                metrics=[acc_1,acc_2,acc_3,acc_4,acc_5,acc_6]

                data=DataBunch(gene_data_train_Tensor.T,)#x_valid
                loss_func = MultiTaskLossWrapper(len(datasetNameList)).to(data)
                learn = Learner(data,ae, loss_func=loss_func, callback_fns=ShowGraph, metrics=metrics)
                learn.split([learn.model.encoder[:6],
                             learn.model.encoder[6:],
                             nn.ModuleList([learn.model.fc1, learn.model.fc2, learn.model.fc3])]);
                learn.freeze()
                '''
                ##################################################
                # Main code
                if multiDatasetMode=="single-task":
                    for task_idx in range(6):  # assuming there are 6 tasks
                        single_task_training_one_epoch(ae, optimizer, criterion, data_loader, task_idx, num_epochs,dataset,batch_size,batch_size_ratio,gene_data_train,path,date,model_dict,AE_loss_list,gene,count)
                else:
                    y_pred_list = None
                    for epoch in range(num_epochs):
                        print("Now epoch:%d"%epoch)
                        t0 = time()
                        for i_data_batch, [images,y_train_T_tensor] in enumerate(data_loader):  # for i, (images, _) in enumerate(data_loader):
                            # flatten the image
                            images = AE.to_var(images.view(images.size(0), -1))
                            images = images.float()
                            if toPrintInfo:
                                print("DEBUG INFO:before the input of model MeiNN")
                                print(images)
                            # out,prediction,embedding = ae(images)

                            out = None
                            y_pred = None
                            y_pred1 = None
                            y_pred2 = None
                            y_pred3 = None
                            y_pred4 = None
                            y_pred5 = None
                            y_pred6 = None
                            embedding = None



                            if multiDatasetMode == "softmax":
                                out, y_pred, embedding = ae(images)#(gene_data_train_Tensor.T)#modified for only partial batch
                                y_masked = y_train_T_tensor
                                y_pred_masked = y_pred
                                if toMask:
                                    mask = y_train_T_tensor.ne(0.5)
                                    # y_masked = torch.masked_select(y_train_T_tensor, mask)
                                    y_masked = y_train_T_tensor * mask
                                    # y_pred_masked = torch.masked_select(prediction, mask)
                                    y_pred_masked = y_pred * mask
                                reg_loss = 0
                                '''
                                for i, param in enumerate(ae.parameters()):
                                    if toPrintInfo:
                                        print("%d-th layer:" % i)
                                        # print(name)
                                        print("param:")
                                        print(param.shape)
                                    reg_loss += torch.sum(torch.abs(param))
                                '''
                                print()
                                reg_loss = return_reg_loss(ae,skip_connection_mode)
                                loss = reg_loss * 0.0001 + criterion(y_pred_masked, y_masked) * 10000 + criterion(out,
                                                                                                                images) * 1

                            elif multiDatasetMode == "multi-task" or multiDatasetMode == "pretrain-finetune":
                                y_pred_masked = y_pred
                                y_masked = y_train_T_tensor
                                y_pred_list = None

                                if len(datasetNameList) == 6:
                                    # out, [y_pred1, y_pred2, y_pred3, y_pred4, y_pred5, y_pred6], embedding=ae(gene_data_train_Tensor.T)
                                    out, y_pred_list, embedding = ae(images)#gene_data_train_Tensor.T)#partial batch
                                    if toValidate:
                                        valid_out, valid_y_pred_list, valid_embedding = ae(gene_data_valid_Tensor.T)  # for validation
                                if len(datasetNameList) == 5:
                                    out, [y_pred1, y_pred2, y_pred3, y_pred4, y_pred5], embedding = ae(images) #gene_data_train_Tensor.T)#partial batch
                                
                                if "umapet" in skip_connection_mode and (epoch+1)%umap_draw_step ==0:
                                    print("embedding.shape")
                                    print(embedding.shape)
                                    draw_umap(embedding.T.cpu().detach().numpy(),y_train,num_of_selected_residue,stage_info="1ststage-train-epo-"+str(epoch),training_setting_info=date)
                                    #draw_umap(out.T.cpu().detach().numpy(),y_train,num_of_selected_residue,stage_info="1ststage-decoderout-train-epo-"+str(epoch),training_setting_info=date)
                                    #draw_umap(y_pred_list.T.cpu().detach().numpy(),y_train,num_of_selected_residue,stage_info="1ststage-decoderout-train-epo-"+str(epoch),training_setting_info=date)
                                '''
                                y_pred1_masked = y_pred1
                                y_pred2_masked = y_pred2
                                y_pred3_masked = y_pred3
                                y_pred4_masked = y_pred4
                                y_pred5_masked = y_pred5
                                y_pred6_masked = y_pred6'''
                                '''
                                y_pred1 = y_pred_list[:,0]
                                y_pred2 = y_pred_list[:,1]
                                y_pred3 = y_pred_list[:,2]
                                y_pred4 = y_pred_list[:,3]
                                y_pred5 = y_pred_list[:,4]
                                y_pred6 = y_pred_list[:,5]'''
                                if toPrintInfo:
                                    print("DEBUG: y_pred_list is:")
                                # print(y_pred_list.shape)
                                    print(len(y_pred_list[0]))
                                # print(y_pred_list[:,0].shape)

                                if toMask:
                                    mask = y_train_T_tensor.ne(0.5)
                                    # y_masked = torch.masked_select(y_train_T_tensor, mask)
                                    y_masked = y_train_T_tensor * mask
                                    # y_pred_masked = torch.masked_select(prediction, mask)
                                    if toPrintInfo:
                                        print("DEBUG:y_train_T_tensor is:")
                                        print(y_train_T_tensor.shape)
                                        # print(y_train_T_tensor)
                                        print("DEBUG: mask is:")
                                        print(mask.shape)
                                        # print(mask)
                                        print("DEBUG: y_masked is:")
                                        print(y_masked.shape)
                                        # print(y_masked)
                                        # print("DEBUG:y_pred1 is:")
                                        # print(y_pred1.shape)
                                        # print(y_pred1)

                                    y_masked_splited = torch.split(y_masked, 1, 1)
                                    mask_splited = torch.split(mask, 1, 1)
                                    if toPrintInfo:
                                        print("len of y_masked_splited%d" % len(y_masked_splited))
                                        print("DEBUG: y_masked_splited is:")
                                        print(y_masked_splited[0].shape)
                                        # print(y_masked_splited)
                                        print("DEBUG: mask_splited is:")
                                        print("len of mask_splited%d" % len(mask_splited))
                                        print(mask_splited[0].shape)

                                    ##############################################
                                    '''
                                    # print(mask_splited)
                                    y_pred_masked_list = []  # [y_pred_list[:,0]*len(datasetNameList)]
                                    loss_list = []  # [y_pred_list[:,0]*len(datasetNameList)]
                                    pred_loss_total_splited_sum = 0
                                    
                                    for i in range(len(datasetNameList)):
                                        # to GPU
                                        y_pred_masked_list.append(y_pred_list[i].to(device).T * (mask_splited[
                                                                                        i].to(device).squeeze()).squeeze())  # y_pred_list[:,i]*mask_splited[i].squeeze())
                                        loss_list.append(
                                            criterion(y_pred_masked_list[i].to(device).T.squeeze(), y_masked_splited[i].to(device).squeeze()))
                                        pred_loss_total_splited_sum += criterion(y_pred_masked_list[i].to(device).T.squeeze(),
                                                                                y_masked_splited[
                                                                                    i].to(device).squeeze())  # loss_list[i]
                                        logger.add_scalar(date+code+" %d-th single dataset %s loss"%(i,datasetNameList[i]), criterion(y_pred_masked_list[i].to(device).T.squeeze(),
                                                                                y_masked_splited[i].to(device).squeeze()), global_step=global_iter_num)
                                        if toPrintInfo:
                                            print("y_pred_masked_list[i]shape")
                                            print(y_pred_masked_list[i].to(device).shape)
                                            print("y_masked_splited[i].squeeze()shape")
                                            print(y_masked_splited[i].to(device).squeeze().shape)
                                            print("loss_list[%d]= %f" % (i, loss_list[i]))
                                            print("pred_loss_total_splited_sum=%f" % pred_loss_total_splited_sum)
                                    '''
                                    #################################################################
                                    if 'accuracy' not in locals().keys():
                                        accuracy=0.0
                                    if 'split_accuracy_list' not in locals().keys():
                                        split_accuracy_list=[0.0 for i in range(len(datasetNameList))]
                                    log_stage_name="1st stage"
                                    y_pred_masked_list,loss_list,pred_loss_total_splited_sum=assign_multi_task_weight(ae,datasetNameList,y_pred_list,y_masked_splited,mask_splited,criterion,(date+code+" "+log_stage_name),[accuracy, split_accuracy_list],
                                            multi_task_training_policy=multi_task_training_policy,skip_connection_mode=skip_connection_mode)
                                    '''
                                    y_pred_masked1 = y_pred1 * mask_splited[0]
                                    y_pred_masked2 = y_pred2 * mask_splited[1]
                                    y_pred_masked3 = y_pred3 * mask_splited[2]
                                    y_pred_masked4 = y_pred4 * mask_splited[3]
                                    y_pred_masked5 = y_pred5 * mask_splited[4]
                                    y_pred_masked6 = y_pred6 * mask_splited[5]
                                    loss1 = criterion(y_pred_masked1, y_masked_splited[0].squeeze())
                                    loss2 = criterion(y_pred_masked2, y_masked_splited[1].squeeze())
                                    loss3 = criterion(y_pred_masked3, y_masked_splited[2].squeeze())
                                    loss4 = criterion(y_pred_masked4, y_masked_splited[3].squeeze())
                                    loss5 = criterion(y_pred_masked5, y_masked_splited[4].squeeze())
                                    loss6 = criterion(y_pred_masked6, y_masked_splited[5].squeeze())
                                    loss_total_splited_sum=loss1+loss2+loss3+loss4+loss5+loss6
                                    '''
                                    '''
                                    y_pred1_df=pd.DataFrame(y_pred1.detach().numpy())
                                    y_pred2_df = pd.DataFrame(y_pred2.detach().numpy())
                                    y_pred3_df = pd.DataFrame(y_pred3.detach().numpy())
                                    y_pred4_df = pd.DataFrame(y_pred4.detach().numpy())
                                    y_pred5_df = pd.DataFrame(y_pred5.detach().numpy())
                                    y_pred6_df = pd.DataFrame(y_pred6.detach().numpy())
                                    y_pred_df=pd.concat( [y_pred1_df, y_pred2_df, y_pred3_df, y_pred4_df, y_pred5_df, y_pred6_df],axis=1)
                                    '''
                                    '''
                                    y_pred=torch.cat([y_pred1, y_pred2, y_pred3, y_pred4, y_pred5, y_pred6],dim=0)
                                    print("y_pred after concat shape")
                                    print(y_pred.shape)
                                    #y_pred=torch.from_numpy(y_pred.to_numpy())
                                    print("mask shape")
                                    print(mask.shape)
                                    print("y_pred shape")
                                    print(y_pred.shape)
                                    y_pred_masked=y_pred*mask
                                    print("y_pred_masked shape")
                                    print(y_pred_masked.shape)
                                    '''
                                    '''
                                    y_pred1_masked = y_pred_masked.iloc[:,0] #y_pred1 * mask
                                    y_pred2_masked = y_pred_masked.iloc[:,1] #y_pred2 * mask
                                    y_pred3_masked = y_pred_masked.iloc[:,2] #y_pred3 * mask
                                    y_pred4_masked = y_pred_masked.iloc[:,3] #y_pred4 * mask
                                    y_pred5_masked = y_pred_masked.iloc[:,4] #y_pred5 * mask
                                    y_pred6_masked = y_pred_masked.iloc[:,5] #y_pred6 * mask'''
                                    # [self.x_train, self.y_train.iloc[:, 0], self.y_train.iloc[:, 1],self.y_train.iloc[:, 2],
                                    # self.y_train.iloc[:, 3], self.y_train.iloc[:, 4], self.y_train.iloc[:, 5]]
                                reg_loss = 0
                                '''
                                for i, param in enumerate(ae.parameters()):
                                    if toPrintInfo:
                                        print("%d-th layer:" % i)
                                        # print(name)
                                        print("param:")
                                        print(param.shape)
                                    reg_loss += torch.sum(torch.abs(param))'''
                                reg_loss = return_reg_loss(ae,skip_connection_mode)

                                # pred_loss = criterion(y_pred_masked, y_masked)
                                '''
                                criterion(y_pred1_masked, y_masked.iloc[:, 0]) +\
                                criterion(y_pred2_masked, y_masked.iloc[:, 1]) +\
                                criterion(y_pred3_masked, y_masked.iloc[:, 2]) +\
                                criterion(y_pred4_masked, y_masked.iloc[:, 3]) +\
                                criterion(y_pred5_masked, y_masked.iloc[:, 4]) +\
                                criterion(y_pred6_masked, y_masked.iloc[:, 5])
                                '''
                                if epoch==1:
                                    print("DEBUG:out dim=",out.shape)
                                    print("DEBUG:images dim=",images.shape)
                                if "MSE" in skip_connection_mode:
                                    criterion_reconstruct=nn.MSELoss()
                                else:
                                    criterion_reconstruct=nn.BCELoss()
                                loss = reg_loss * 0.0001 + pred_loss_total_splited_sum * 100000 + criterion_reconstruct(out, images) * 1
                                if "#" in skip_connection_mode:
                                    contrastive_criterion=SupConLoss()
                                    loss+= contrastive_criterion(embedding)*CONTRASTIVE_FACTOR
                                if "VAE" in skip_connection_mode:
                                    loss += ae.kl_divergence
                                log_stage_name=""
                                if toValidate:
                                    normalized_pred_out, num_wrong_pred, accuracy, split_accuracy_list,auroc_list = tools.evaluate_accuracy_list(
                                        datasetNameList, valid_label,
                                        valid_y_pred_list,toPrint=False)  # added for validation data#2023-1-8
                                    if "ROnP" in multi_task_training_policy:
                                        scheduler.step(accuracy)
                                    logger.add_scalar(
                                        date + code + " " + log_stage_name + ": total validation accuracy",
                                        accuracy, global_step=global_iter_num)
                                    for i in range(len(datasetNameList)):  # added for validation data#2023-1-8
                                        logger.add_scalar(
                                            date + code + " " + log_stage_name + ": %d-th single dataset %s validation accuracy" % (
                                                i, datasetNameList[i]),
                                            split_accuracy_list[i], global_step=global_iter_num)
                                logger.add_scalar(date+code+" autoencoder reconstruction loss", criterion_reconstruct(out, images), global_step=global_iter_num)
                                logger.add_scalar(date+code+" regularization loss", reg_loss, global_step=global_iter_num)
                                logger.add_scalar(date+code+" classifier predction loss", pred_loss_total_splited_sum, global_step=global_iter_num)
                                logger.add_scalar(date+code+" total train loss", loss.item(), global_step=global_iter_num)
                                for name, param in ae.named_parameters():
                                    logger.add_histogram(date+code+name, param.data.cpu().numpy(), global_step=global_iter_num)
                            # loss= nn.BCELoss(prediction,y_train_T_tensor)+nn.BCELoss(out,images)

                            def BCE_loss_masked(y_pred, y):
                                # y_pred:预测标签，已经过sigmoid/softmax处理 shape is (batch_size, 1)
                                # y：真实标签（一般为0或1） shape is (batch_size)
                                mask = y.ne(0.5)
                                y_masked = torch.masked_select(y, mask)
                                y_pred_masked = torch.masked_select(y_pred, mask)

                                y_pred_masked = torch.cat((1 - y_pred_masked, y_pred_masked),1)  # 将二种情况的概率都列出，y_hat形状变为(batch_size, 2)
                                # 按照y标定的真实标签，取出预测的概率，来计算损失
                                return - torch.log(y_pred_masked.gather(1, y_masked.view(-1, 1))).mean()
                                # 函数返回loss均值

                            optimizer.zero_grad()
                            loss.backward()
                            optimizer.step()
                            global_iter_num = epoch * len(
                                data_loader) + i_data_batch + 1  # calculate it's which step start from training
                            if "*" in skip_connection_mode:
                                ae.save_site_gene_pathway_weight_visualization(info=" epoch "+str(global_iter_num))
                            if mask_option is not None and (epoch+1)%evaluate_weight_site_pathway_step ==0:
                                my_gene_to_residue_info.evaluate_weight_site_pathway(ae,date+"1st-epo"+str(epoch))
                            if toPrintInfo:
                                print("y_pred_list[0].shape")
                                print(y_pred_list[0].shape)
                                # print(y_pred_list)
                                print("y_train.T")
                                print(y_train.T.shape)
                                # print(y_train.T)
                                print("y_pred_masked_list[0] shape:")
                                print(y_pred_masked_list[0].shape)
                                # print(y_pred_masked_list)
                                print("y_masked")
                                print(y_masked.shape)
                                # print(y_masked)
                                toPrintInfo = False
                            # y_pred_list=np.array(y_pred_list)
                            
                            input_tensor=torch.Tensor([item.cpu().detach().numpy() for item in y_pred_list]).squeeze().T
                            target_tensor=y_train_T_tensor
                            # Assuming 'input_tensor' is the input tensor and 'target_tensor' is the target tensor
                            if target_tensor.shape != input_tensor.shape:
                                # Reshape the target tensor to match the shape of the input tensor
                                target_tensor = target_tensor.view(input_tensor.shape)

                            print("reg_loss%f,ae loss%f,prediction loss-masked%f,prediction loss%f"
                                % (reg_loss,criterion_reconstruct(out,images),pred_loss_total_splited_sum,criterion(input_tensor, target_tensor)))#originally#torch.Tensor([item.cpu().detach().numpy() for item in y_pred_list]).squeeze().T

                            print("loss: %f" % loss.item())
                            # print(loss.item())
                            AE_loss_list.append(loss.item())

                            if (i + 1) % 10 == 0:
                                print('Epoch [%d/%d], Iter [%d/%d] Loss: %.4f Time: %.2fs'
                                    % (epoch + 1, num_epochs, i + 1, len(dataset) // batch_size, loss.item(),
                                        time() - t0))  # original version: loss.item() was loss.data[0]
                                
                        if (epoch + 1) % 1 == 0 and batch_size_ratio==1.0:#batch_size_ratio added
                            # save the reconstructed images
                            fixed_x = fixed_x.float()
                            reconst_images, y_pred, embedding = ae(fixed_x)  # prediction
                            reconst_images = reconst_images.view(reconst_images.size(0), gene_data_train.shape[
                                0])  # reconst_images = reconst_images.view(reconst_images.size(0), 1, 28, 28)
                            # mydir = 'E:/JI/4 SENIOR/2021 fall/VE490/ReGear-gyl/ReGear/test_sample/data/'
                            mkpath = ".\\result\\%s" % date
                            mkdir(mkpath)
                            myfile = 'rcnst_img_bt%d_ep%d.png' % (i + 1, (epoch + 1))
                            reconst_images_path = os.path.join(mkpath, myfile)
                            torchvision.utils.save_image(reconst_images.data.cpu(), reconst_images_path)
                        ##################
                        model = model_dict[model_type]()
                    for i, param in enumerate(ae.parameters()):
                        print("%d-th layer:" % i)
                        print("param:")
                        print(param.shape)
                    torch.save({"epoch": num_epochs,  # 一共训练的epoch
                                "model_state_dict": ae.state_dict(),  # 保存模型参数×××××这里埋个坑××××
                                "optimizer": optimizer.state_dict()}, path + date + '.tar')

                    torch.save(ae, path + date + '.pth')  # save the whole autoencoder network
                    AE_loss_list_df = pd.DataFrame(AE_loss_list)
                    AE_loss_list_df.to_csv(path + date + "_AE_loss_list).csv", sep='\t')
                    if count == 1:
                        with open(path + date + '_train_model_pytorch.pickle', 'wb') as f:
                            pickle.dump((gene, ae), f)  # pickle.dump((gene, model), f)
                    else:
                        with open(path + date + '_train_model_pytorch.pickle', 'ab') as f:
                            pickle.dump((gene, ae), f)  # pickle.dump((gene, model), f)

    ###################################pretrain-finetune##################################################
                    if multiDatasetMode == "pretrain-finetune":
                        print("now we train single classifier:")
                        pth_name="single-classifier-trained"
                        loss_single_classifier_loss_list=[]#list([],[],[],[],[],[])
                        for dataset_id, datasetName in enumerate(datasetNameList):
                            print("The %d-th dataset"%dataset_id)
                            for param in ae.parameters():
                                if toPrintInfo:
                                    print("#"*100)
                                    print(param)
                                    print("#" * 100)
                                param.requires_grad = False
                            if dataset_id == 0:
                                for param in ae.FCN1.parameters():
                                    param.requires_grad = True
                            if dataset_id == 1:
                                for param in ae.FCN2.parameters():
                                    param.requires_grad = True
                            if dataset_id == 2:
                                for param in ae.FCN3.parameters():
                                    param.requires_grad = True
                            if dataset_id == 3:
                                for param in ae.FCN4.parameters():
                                    param.requires_grad = True
                            if dataset_id == 4:
                                for param in ae.FCN5.parameters():
                                    param.requires_grad = True
                            if dataset_id == 5:
                                for param in ae.FCN6.parameters():
                                    param.requires_grad = True
                            for epoch in range(num_epochs):
                                for i_data_batch, (images,y_train_T_tensor) in enumerate(data_loader):  # for i, (images, _) in enumerate(data_loader):
                                    # flatten the image
                                    images = AE.to_var(images.view(images.size(0), -1))
                                    images = images.float()
                                    #forward
                                    if len(datasetNameList) == 6:
                                        out, y_pred_list, embedding = ae(images)#gene_data_train_Tensor.T)#partial batch
                                        if toValidate:
                                            valid_out, valid_y_pred_list, valid_embedding = ae(gene_data_valid_Tensor.T)  # for validation
                                    
                                    ##umap
                                    if "umapet" in skip_connection_mode and (epoch+1)%umap_draw_step ==0:
                                        print("embedding.shape")
                                        print(embedding.shape)
                                        draw_umap(embedding.T.cpu().detach().numpy(),y_train,num_of_selected_residue,stage_info="2ndstage-%d-th-dataset-%s-train-epo-"%(dataset_id,datasetName)+str(epoch),training_setting_info=date)
                                    ##
                                    if mask_option is not None and (epoch+1)%evaluate_weight_site_pathway_step ==0:
                                        my_gene_to_residue_info.evaluate_weight_site_pathway(ae,date+"2nd-sg-epo"+str(epoch))
                                    if toMask:
                                        mask = y_train_T_tensor.ne(0.5)
                                        y_masked = y_train_T_tensor * mask
                                        if toPrintInfo:
                                            print("DEBUG:y_train_T_tensor is:")
                                            print(y_train_T_tensor.shape)
                                            print("DEBUG: mask is:")
                                            print(mask.shape)
                                            print("DEBUG: y_masked is:")
                                            print(y_masked.shape)
                                        y_masked_splited = torch.split(y_masked, 1, 1)
                                        mask_splited = torch.split(mask, 1, 1)
                                        if toPrintInfo:
                                            print("len of y_masked_splited%d" % len(y_masked_splited))
                                            print("DEBUG: y_masked_splited is:")
                                            print(y_masked_splited[0].shape)
                                            print("DEBUG: mask_splited is:")
                                            print("len of mask_splited%d" % len(mask_splited))
                                            print(mask_splited[0].shape)
                                        ###############################################
                                        y_pred_masked_list = []  # [y_pred_list[:,0]*len(datasetNameList)]
                                        loss_list = []  # [y_pred_list[:,0]*len(datasetNameList)]
                                        pred_loss_total_splited_sum = 0
                                        loss_single_classifier = 0
                                        for i in range(len(datasetNameList)):
                                            y_pred_masked_list.append(y_pred_list[i].to(device).T * (mask_splited[i].to(device).squeeze()).squeeze())
                                            loss_list.append(criterion(y_pred_masked_list[i].to(device).T.squeeze(), y_masked_splited[i].to(device).squeeze()))
                                            pred_loss_total_splited_sum += criterion(y_pred_masked_list[i].to(device).T.squeeze(),y_masked_splited[i].to(device).squeeze())
                                        ###############################################
                                    reg_loss=return_reg_loss(ae,skip_connection_mode)
                                    loss_single_classifier=pred_loss_total_splited_sum*100000+reg_loss*0.0001
                                    if "#" in skip_connection_mode:
                                        contrastive_criterion=SupConLoss()
                                        loss_single_classifier+= contrastive_criterion(embedding)*CONTRASTIVE_FACTOR
                                    if "VAE" in skip_connection_mode:
                                        loss_single_classifier += ae.kl_divergence
                                    print(pth_name+"loss: %f" % loss_single_classifier.item())
                                    optimizer=torch.optim.Adam(filter(lambda p: p.requires_grad, ae.parameters()), lr=learning_rate_list[1])#1e-3

                                    if "ROnP" in multi_task_training_policy:
                                        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'max',factor=0.9,patience=40) # added for special training policy

                                    optimizer.zero_grad()
                                    loss_single_classifier.backward(retain_graph=True)
                                    #loss_single_classifier_loss_list[dataset_id].append(loss_single_classifier.item())
                                    optimizer.step()
                                    global_iter_num = epoch * len(data_loader) + i_data_batch + 1  # calculate it's which step start from training
                                    log_stage_name="single-classifier training stage"
                                    if "*" in skip_connection_mode:
                                        ae.save_site_gene_pathway_weight_visualization(info=log_stage_name+" epoch "+str(global_iter_num))
                                    
                                    if toValidate:
                                        normalized_pred_out, num_wrong_pred, accuracy, split_accuracy_list,auroc_list = tools.evaluate_accuracy_list(
                                            datasetNameList, valid_label,
                                            valid_y_pred_list,toPrint=False)  # added for validation data#2023-1-8
                                        if "ROnP" in multi_task_training_policy:
                                            scheduler.step(split_accuracy_list[dataset_id])
                                        logger.add_scalar(
                                            date + code + " " + log_stage_name + ": total validation accuracy",
                                            accuracy, global_step=global_iter_num)
                                        for i in range(len(datasetNameList)):  # added for validation data#2023-1-8
                                            logger.add_scalar(
                                                date + code + " " + log_stage_name + ": %d-th single dataset %s validation accuracy" % (
                                                i, datasetNameList[i]),
                                                split_accuracy_list[i], global_step=global_iter_num)
                                    logger.add_scalar(date+code+" single-classifier training stage: autoencoder reconstruction loss",
                                                    criterion(out, images), global_step=global_iter_num)
                                    logger.add_scalar(date+code+" single-classifier training stage: regularization loss", reg_loss,
                                                    global_step=global_iter_num)
                                    logger.add_scalar(date+code+" single-classifier training stage: classifier predction loss",
                                                    pred_loss_total_splited_sum, global_step=global_iter_num)
                                    logger.add_scalar(date+code+" single-classifier training stage: total train loss",
                                                    loss_single_classifier.item(), global_step=global_iter_num)
                                    for name, param in ae.named_parameters():
                                        logger.add_histogram(date+code+" single-classifier training stage: " + name,
                                                            param.data.cpu().numpy(), global_step=global_iter_num)

                        torch.save(ae, path + date+pth_name+".pth")
                    ##########################3rd stage train all parameters#################################################################    
                        for param in ae.parameters():
                            param.requires_grad = True
                        ae,loss_list,global_iter_num=single_train_process(num_epochs, data_loader, datasetNameList, ae, images.T, toMask,
                                            y_train_T_tensor, criterion,path,date,pth_name="finetune",toDebug=False,global_iter_num=global_iter_num,log_stage_name="whole",code=code,
                                                            toValidate=toValidate,gene_data_valid_Tensor=gene_data_valid_Tensor,valid_label=valid_label,multi_task_training_policy=multi_task_training_policy,
                                                            learning_rate_list=learning_rate_list,skip_connection_mode=skip_connection_mode,umap_draw_step=umap_draw_step,num_of_selected_residue=num_of_selected_residue,y_train=y_train,mask_option=mask_option,my_gene_to_residue_info=my_gene_to_residue_info)#images originally:,gene_data_train_Tensor


                        ###evaluate the mask#####
                        if mask_option is not None:
                            my_gene_to_residue_info.evaluate_weight_site_pathway(ae,date+"-final")
                            '''
                            (pathway_learned_percentile_list, 
                            pathway_average_learned_percentile, 
                            pathway_all_weights, pathway_ones_distribution, 
                            pathway_zeros_distribution, pathway_masked_distribution) = my_gene_to_residue_info.evaluate_weight(ae.decoder1[0].weight.T, 0.05, part_option="path", data_name=date+"final")

                            print("pathway_learned_percentile_list:", pathway_learned_percentile_list)
                            print("pathway_average_learned_percentile:", pathway_average_learned_percentile)
                            print("pathway_all_weights:", pathway_all_weights)
                            print("pathway_ones_distribution:", pathway_ones_distribution)
                            print("pathway_zeros_distribution:", pathway_zeros_distribution)
                            print("pathway_masked_distribution:", pathway_masked_distribution)

                            (site_learned_percentile_list, 
                            site_average_learned_percentile,
                            site_all_weights, site_ones_distribution, 
                            site_zeros_distribution, site_masked_distribution) = my_gene_to_residue_info.evaluate_weight(ae.decoder2[0].weight.T, 0.05, part_option="site", data_name=date+"final")

                            print("site_learned_percentile_list:", site_learned_percentile_list)
                            print("site_average_learned_percentile:", site_average_learned_percentile)
                            print("site_all_weights:", site_all_weights)
                            print("site_ones_distribution:", site_ones_distribution)
                            print("site_zeros_distribution:", site_zeros_distribution)
                            print("site_masked_distribution:", site_masked_distribution)'''


                            
                    '''
                    myMeiNN = MeiNN_pytorch(config, path, date, code, gene_data_train.T, y_train.T, platform, model_type, data_type,
                                    HIDDEN_DIMENSION, toTrainMeiNN, AE_epoch_from_main=AE_epoch_from_main,
                                    NN_epoch_from_main=NN_epoch_from_main, separatelyTrainAE_NN=separatelyTrainAE_NN,
                                    model_dir='./results/models',
                                    gene_to_residue_or_pathway_info=my_gene_to_residue_info, toAddGeneSite=toAddGeneSite,
                                    toAddGenePathway=toAddGenePathway,
                                    multiDatasetMode=multiDatasetMode, datasetNameList=datasetNameList, lossMode=lossMode)

                    # myMeiNN.build()
                    myMeiNN.compile()
                    # myMeiNN.fcn.fit(gene_data_train.T, y_train.T, epochs=NN_epoch_from_main, batch_size=79, shuffle=True)
                    myMeiNN.fit()'''

                if toAddGenePathway and False:
                    print("***************************")
                    print("len residuals_name%d" % len(residuals_name))

                    print("****gene_pathway_df***********************")
                    print(gene_pathway_df)
                    print("****csv_data***********************")
                    print(gene_pathway_csv_data)
                    print("****gene_name_data***********************")
                    print(gene_name_data)
                    print(gene_name_data.iloc[1])
                    print("****gene_present_list_df***********************")
                    print(gene_present_list_df)
                    print("****gene_present_index***********************")
                    print(gene_present_index)
                    # print("****gene_present_index_sorted***********************")
                    # print(gene_present_index_sorted)
                    print("****gene_pathway_present_gene_index***********************")
                    print(gene_pathway_present_gene_index)

                    # pathway_name_data

            '''
            decoder_regularizer='var_l1'
            decoder_regularizer_initial=0.0001
            activ = 'relu'
            latent_scale=5
            l_rate=K.variable(0.01)
            relu_thresh=0
            decoder_bn=False
            decoder_bias='last'
            last_activ='tanh'#'softmax'
            in_dim = 809
            # Compress the dimension to latent_dim
            mid_dim = math.sqrt(in_dim *  latent_dim)
            q3_dim =math.sqrt(in_dim * mid_dim)
            q1_dim=math.sqrt( latent_dim * mid_dim)
            decoder_shape=[ latent_dim,q1_dim,mid_dim,q3_dim]
            input_shape=(809)
            if decoder_regularizer == 'dot_weights':
                dot_weights = np.zeros(shape=(latent_scale * latent_dim, latent_scale * latent_dim))
                for s in range(latent_dim):
                    dot_weights[s * latent_scale:s * latent_scale + latent_scale,
                    s * latent_scale:s * latent_scale + latent_scale] = 1
            # L1 regularizer with the scaling factor updateable through the l_rate variable (callback)
            def variable_l1(weight_matrix):
                return l_rate * K.sum(K.abs(weight_matrix))
            # L2 regularizer with the scaling factor updateable through the l_rate variable (callback)
            def variable_l2(weight_matrix):
                return l_rate * K.sum(K.square(weight_matrix))
            # Mixed L1 and L2 regularizer, updateable scaling. TODO: Consider implementing different scaling factors for L1 and L2 part
            def variable_l1_l2(weight_matrix):
                return l_rate * (K.sum(K.abs(weight_matrix)) + K.sum(K.square(weight_matrix))) * 0.5
            # Dot product-based regularizer
            def dotprod_weights(weights_matrix):
                penalty_dot = l_rate * K.mean(K.square(K.dot(weights_matrix,
                                                                  K.transpose(weights_matrix)) * dot_weights))
                penalty_l1 = 0.000 * l_rate * K.sum(K.abs(weights_matrix))
                return penalty_dot + penalty_l1
            def dotprod(weights_matrix):
                penalty_dot = l_rate * K.mean(K.square(K.dot(weights_matrix, K.transpose(weights_matrix))))
                penalty_l1 = 0.000 * l_rate * K.sum(K.abs(weights_matrix))
                return penalty_dot + penalty_l1
            def dotprod_inverse(weights_matrix):
                penalty_dot = 0.1 * K.mean(
                    K.square(K.dot(K.transpose(weights_matrix), weights_matrix) * dot_weights))
                penalty_l1 = 0.000 * l_rate * K.sum(K.abs(weights_matrix))
                return penalty_dot + penalty_l1
            def relu_advanced(x):
                return K.relu(x, threshold=relu_thresh)
            if activ == 'relu':
                activ = relu_advanced
            # assigns the regularizer to the scaling factor. TODO: Look for more elegant method
            if decoder_regularizer == 'var_l1':
                reg = variable_l1
                reg1 = variable_l1
            elif decoder_regularizer == 'var_l2':
                reg = variable_l2
                reg1 = variable_l2
            elif decoder_regularizer == 'var_l1_l2':
                reg = variable_l1_l2
                reg1 = variable_l1_l2
            elif decoder_regularizer == 'l1':
                reg = regularizers.l1(decoder_regularizer_initial)
                reg1 = regularizers.l1(decoder_regularizer_initial)
            elif decoder_regularizer == 'l2':
                reg = regularizers.l2(decoder_regularizer_initial)
                reg1 = regularizers.l2(decoder_regularizer_initial)
            elif decoder_regularizer == 'l1_l2':
                reg = regularizers.l1_l2(l1=decoder_regularizer_initial, l2=decoder_regularizer_initial)
                reg1 = regularizers.l1_l2(l1=decoder_regularizer_initial, l2=decoder_regularizer_initial)
            elif decoder_regularizer == 'dot':
                reg = dotprod
                reg1 = dotprod
            elif decoder_regularizer == 'dot_weights':
                reg1 = dotprod_weights
                reg = dotprod
            else:
                reg = None
                reg1 = None
            # this is our input placeholder
            input = Input(shape=(in_dim,))
            # 编码层
            encoded = Dense(q3_dim, activation='relu')(input)
            encoded = Dense(mid_dim, activation='relu')(encoded)
            encoded = Dense(q1_dim, activation='relu')(encoded)
            encoder_output = Dense( latent_dim,name="input_to_encoding")(encoded)
            decoded = layers.Dense(q1_dim,
                             activation=activ,
                             name='Decoder1',
                             activity_regularizer=reg1)(encoder_output)
            if decoder_bn:
                decoded = layers.BatchNormalization()(decoded)
            # adds layers to the decoder. See encoder layers
            if len(decoder_shape) > 1:
                for i in range(len(decoder_shape) - 1):
                    if decoder_bias == 'all':
                        decoded = layers.Dense(decoder_shape[i + 1],
                                         activation=activ,
                                         name='Dense_D' + str(i + 2),
                                         use_bias=True,
                                         activity_regularizer=reg)(decoded)
                    else:
                        decoded = layers.Dense(decoder_shape[i + 1],
                                         activation=activ,
                                         name='Dense_D' + str(i + 2),
                                         use_bias=False,
                                         kernel_regularizer=reg)(decoded)
                    if decoder_bn:
                        decoded = layers.BatchNormalization()(decoded)
            if decoder_bias == 'none':
                ae_outputs = layers.Dense(input_shape,
                                              activation=last_activ,
                                              use_bias=False,name='ae_output')(decoded)
            else:
                ae_outputs = layers.Dense(input_shape,
                                              activation=last_activ,name='ae_output')(decoded)
            # 解码层
            #decoded = Dense(q1_dim, activation='relu')(encoder_output)
            #decoded = Dense(mid_dim, activation='relu')(decoded)
            #decoded = Dense(q3_dim, activation='relu')(decoded)
            #decoded = Dense(in_dim, activation='tanh')(decoded)
            # 构建自编码模型
            autoencoder = Model(inputs=input, outputs=ae_outputs)
            # 构建编码模型
            encoder = Model(inputs=input, outputs=encoder_output)
            # compile autoencoder
            autoencoder.compile(optimizer='adam', loss='binary_crossentropy') #loss='mse'
            class CustomAutoencoder(layers.Layer):
                def __init__(self):
                    super(CustomAutoencoder, self).__init__()
                    # this is our input placeholder
                    input = Input(shape=(in_dim,))
                    # 编码层
                    encoded = Dense(q3_dim, activation='relu')(input)
                    encoded = Dense(mid_dim, activation='relu')(encoded)
                    encoded = Dense(q1_dim, activation='relu')(encoded)
                    encoder_output = Dense(latent_dim, name="input_to_encoding")(encoded)
                    decoded = layers.Dense(q1_dim,
                                           activation=activ,
                                           name='Decoder1',
                                           activity_regularizer=reg1)(encoder_output)
                    if decoder_bn:
                        decoded = layers.BatchNormalization()(decoded)
                    # adds layers to the decoder. See encoder layers
                    if len(decoder_shape) > 1:
                        for i in range(len(decoder_shape) - 1):
                            if decoder_bias == 'all':
                                decoded = layers.Dense(decoder_shape[i + 1],
                                                       activation=activ,
                                                       name='Dense_D' + str(i + 2),
                                                       use_bias=True,
                                                       activity_regularizer=reg)(decoded)
                            else:
                                decoded = layers.Dense(decoder_shape[i + 1],
                                                       activation=activ,
                                                       name='Dense_D' + str(i + 2),
                                                       use_bias=False,
                                                       kernel_regularizer=reg)(decoded)
                            if decoder_bn:
                                decoded = layers.BatchNormalization()(decoded)
                    if decoder_bias == 'none':
                        self.ae_outputs = layers.Dense(input_shape,
                                                  activation=last_activ,
                                                  use_bias=False, name='ae_output')(decoded)
                    else:
                        self.ae_outputs = layers.Dense(input_shape,
                                                  activation=last_activ, name='ae_output')(decoded)
                    self.autoencoder = Model(inputs=input, outputs=ae_outputs)
                    # 构建编码模型
                    self.encoder = Model(inputs=input, outputs=encoder_output)
                def call(self, inputs,option='ae_output'):
                    if(option=='ae_output'):
                        return self.autoencoder(input)
                    elif(option=='embedding'):
                        return self.encoder(input)
            # training
            '''

            '''
            MeiNN.autoencoder.fit(gene_data_train.T, gene_data_train.T, epochs=AE_epoch_from_main, batch_size=79, shuffle=True)
            print("AE finish_fitting")
            MeiNN.autoencoder.save(date+'AE.h5')
            print("AE finish saving model")


            ################################################################
            #the following is the embedding to y prediction
            #ae=torch.load(date+'_auto-encoder.pth')
            #loaded_autoencoder = load_model(date + 'AE.h5',custom_objects={'variable_l1': variable_l1,'relu_advanced':relu_advanced})
            input_to_encoding_model = Model(inputs=autoencoder.input,
                                       outputs=autoencoder.get_layer('input_to_encoding').output)
            print("input_to_encoding_model.predict(gene_data_train.T)")
            print(input_to_encoding_model.predict(gene_data_train.T))
            # embedding=ae.code(torch.tensor(gene_data_train.T).float())
            embedding = input_to_encoding_model.predict(gene_data_train.T)
            embedding_df = pd.DataFrame(embedding)
            embedding_df.to_csv(path+date+"_"+code + "_gene_level" + "(" + data_type + '_' + model_type + "_embedding_original).txt", sep='\t')
            print("embedding is ")
            print(embedding)
            print(embedding.shape)
            in_dim =  latent_dim
            # output dimension is 1
            out_dim = 1
            mid_dim = math.sqrt(in_dim *  latent_dim)
            q3_dim = math.sqrt(in_dim * mid_dim)

            q1_dim = math.sqrt( latent_dim * mid_dim)
            # this is our input placeholder
            #input = Input(shape=(in_dim,))
            # 编码层
            out_x = Dense(q3_dim, activation='relu')(encoder_output)
            out_x = Dense(mid_dim, activation='relu')(out_x)
            out_x = Dense(q1_dim, activation='relu')(out_x)
            output = Dense(out_dim,activation='sigmoid',name="prediction")(out_x)#originally sigmoid
            def reconstruct_and_predict_loss(x,ae_outputs,output,y_train,y_index):
                reconstruct_loss = losses.binary_crossentropy(x, ae_outputs)
                print(output[0])
                print("y_train.T=")
                print(y_train.T)
                print("y_train.T.shape=")
                print(y_train.T.shape)
                predict_loss =losses.binary_crossentropy(y_pred=output,y_true=y_train.T[y_index]) #- 0.5 * K.mean(1 + z_log_sigma - K.square(z_mean) - K.exp(z_log_sigma), axis=-1)
                return reconstruct_loss + predict_loss
            def my_reconstruct_and_predict_loss(y_true, y_pred, lam=0.5):
                reconstruct_loss = losses.binary_crossentropy(y_true=autoencoder.input, y_pred=autoencoder.get_layer('ae_output').output)
                predict_loss = losses.binary_crossentropy(y_true,
                                                          y_pred)  # - 0.5 * K.mean(1 + z_log_sigma - K.square(z_mean) - K.exp(z_log_sigma), axis=-1)
                return K.mean(lam * reconstruct_loss + (1 - lam) * predict_loss)
            # build the fcn model
            fcn = Model(inputs=input, outputs=output)
            # compile fcn
            fcn.compile(optimizer='adam', loss= my_reconstruct_and_predict_loss,experimental_run_tf_function=False)  # loss='mse'#'binary_crossentropy'
            # training
            #fcn.fit(embedding, y_train.T, epochs=NN_epoch_from_main, batch_size=79, shuffle=True)
            fcn.fit(gene_data_train.T, y_train.T, epochs=NN_epoch_from_main, batch_size=79, shuffle=True)
            print("FCN finish_fitting")
            fcn.save(path+date + 'FCN.h5')
            print("FCN finish saving model")
            embedding = input_to_encoding_model.predict(gene_data_train.T)  # input_to_encoding_model.predict(gene_data_train.T)
            embedding_df = pd.DataFrame(embedding)
            embedding_df.to_csv(
                path+date + "_" + code + "_gene_level" + "(" + data_type + '_' + model_type + "_embedding_trained).txt",
                sep='\t')
            print("embedding is ")
            print(embedding)
            print(embedding.shape)
            '''
            '''
            num_epochs = NN_epoch_from_main
            batch_size = 79 # gene_data_train.shape[0]#100#809
            hidden_size = 10
            dataset = gene_data_train.T  # .flatten()#gene_data_train.view(gene_data_train.size[0], -1)
            # dataset = gene_data_train  # dsets.MNIST(root='../data',
            # train=True,
            # transform=transforms.ToTensor(),
            # download=True)
            data_loader = torch.utils.data.DataLoader(dataset=dataset,
                                                      batch_size=batch_size,
                                                      shuffle=True)
            print("gene_data_train.shape")
            print(gene_data_train.shape)
            print("dataset.shape")
            print(dataset.shape)
            #ae = AE.Autoencoder(in_dim=gene_data_train.shape[0], h_dim=79 * 5)  # in_dim=gene_data_train.shape[1]
            fcn=AE.NN(in_dim=HIDDEN_DIMENSION, h_dim=1)
            if torch.cuda.is_available():
                fcn.cuda()
            criterion = nn.BCELoss()
            optimizer = torch.optim.Adam(fcn.parameters(), lr=0.001)
            iter_per_epoch = len(data_loader)
            data_iter = iter(data_loader)
            # save fixed inputs for debugging
            fixed_x = next(data_iter)  # fixed_x, _ = next(data_iter)
            mydir = 'E:/JI/4 SENIOR/2021 fall/VE490/ReGear-gyl/ReGear/test_sample/data/'
            myfile = '%snn_real_image_%s_batch%d.png' % (date,code, i + 1)
            images_path = os.path.join(mydir, myfile)
            torchvision.utils.save_image(Variable(fixed_x).data.cpu(), images_path)
            fixed_x = AE.to_var(fixed_x.view(fixed_x.size(0), -1))
            NN_loss_list=[]
            for epoch in range(num_epochs):
                t0 = time()
                for i, (images) in enumerate(data_loader):  # for i, (images, _) in enumerate(data_loader):
                    # flatten the image
                    images = AE.to_var(images.view(images.size(0), -1))
                    images = images.float()
                    #embedding
                    embedding_=ae.code(images)
                    out = fcn(embedding_)
                    #print("out at tain.py nn ")
                    #print(out)
                    #print("torch.tensor(y_train).float() at tain.py nn ")
                    #print(torch.tensor(y_train).float())
                    out=torch.reshape(out, (-1,))
                    loss = criterion(out, torch.tensor(y_train).float().T)
                    optimizer.zero_grad()
                    loss.backward()
                    optimizer.step()
                    print("training nn, epoch %d : loss= "% epoch)
                    print(loss.item())
                    NN_loss_list.append(loss.item())
                    if (i + 1) % 100 == 0:
                        print('Epoch [%d/%d], Iter [%d/%d] Loss: %.4f Time: %.2fs'
                              % (epoch + 1, num_epochs, i + 1, len(dataset) // batch_size, loss.item(),
                                 time() - t0))  # original version: loss.item() was loss.data[0]
                        print("out after reshape")
                        print(out.shape)
                        print(out)
                if (epoch + 1) % 1 == 0:
                    fixed_x = fixed_x.float()
                    embedding_out = ae.code(torch.tensor(fixed_x).float())
                    reconst_images = fcn(embedding_out)
                    reconst_images = reconst_images.view(reconst_images.size(0),
                                                         -1)  # reconst_images = reconst_images.view(reconst_images.size(0), 1, 28, 28)
                    mydir = 'E:/JI/4 SENIOR/2021 fall/VE490/ReGear-gyl/ReGear/test_sample/data/'
                    myfile = '%snn_reconst_images_%s_batch%d_epoch%d.png' % (date,code, i + 1, (epoch + 1))
                    reconst_images_path = os.path.join(mydir, myfile)
                    torchvision.utils.save_image(reconst_images.data.cpu(), reconst_images_path)
            torch.save(fcn, date+'_fully-connected-network.pth')
            NN_loss_list_df = pd.DataFrame(NN_loss_list)
            NN_loss_list_df.to_csv(
                date + "_" + code + "_gene_level" + "(" + data_type + '_' + model_type + "_NN_loss).csv",
                sep='\t')
        '''

    else:
        model = model_dict[model_type]()
        model.fit(gene_data_train.T, y_train)
        if model_type == "RandomForest":
            print("The number of residuals involved in the gene {} is {}".format(gene, len(gene_data_train)))
            print("The feature importance is ")
            print(model.feature_importances_)
            print("The names of residuals are ")
            print(residuals_name)
            print(15 * '-')

        if count == 1:
            with open(path + date + "_" + code + "_train_model.pickle", 'wb') as f:#path + date + "_" + code + "_" + model_type + "_" + data_type + 'train_model.pickle'
                pickle.dump((gene, model), f)
        else:
            with open(path + date + "_" + code + "_train_model.pickle", 'ab') as f:
                pickle.dump((gene, model), f)
    print("Training finish!")
    return myMeiNN, residuals_name


def train_VAE(model, train_db, optimizer=tf.keras.optimizers.Adam(0.001), n_input=80):
    for epoch in range(1000):
        for step, x in enumerate(train_db):
            x = tf.reshape(x, [-1, n_input])
            with tf.GradientTape() as tape:
                x_rec_logits, mean, log_var = model(x)
                rec_loss = tf.losses.binary_crossentropy(x, x_rec_logits, from_logits=True)
                rec_loss = tf.reduce_mean(rec_loss)
                # compute kl divergence (mean, val) ~ N(0, 1)
                kl_div = -0.5 * (log_var + 1 - mean ** 2 - tf.exp(log_var))
                kl_div = tf.reduce_mean(kl_div) / x.shape[0]
                # loss
                loss = rec_loss + 1.0 * kl_div

            grads = tape.gradient(loss, model.trainable_variables)
            optimizer.apply_gradients(zip(grads, model.trainable_variables))

            if step % 10 == 0:
                print(epoch, step, 'kl_div:', float(kl_div), 'rec_loss:', rec_loss)


if __name__ == '__main__':
    # Parameter description：
    # code: dataSet ID such as GSE66695 ( string )
    # train_file: train data filename( .txt )
    # label_file: train label filename(.txt)
    # platform: Gene correspond to methylation characteristics( json file )
    # model_type: type of regression model ( string )
    # data_type: type of data ( string )

    # example

    code = "GSE66695"
    train_file = "data_train.txt"
    label_file = "label_train.txt"
    platform = "platform.json"
    model_type = "LinearRegression"
    data_type = "origin_data"

    train_data = pd.read_table(train_file, index_col=0)
    train_label = pd.read_table(label_file, index_col=0).values.ravel()

    run(code, train_data, train_label, platform, model_type, data_type)
