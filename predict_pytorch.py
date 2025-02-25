import re
import os
import json
import numpy as np
import pandas as pd
import torch
from scipy import stats
import pickle
from sklearn.linear_model import LinearRegression
from sklearn.linear_model import LogisticRegression
from sklearn.linear_model import Lasso
from sklearn.linear_model import Ridge
from torch import nn

import AutoEncoder as AE
import warnings

warnings.filterwarnings("ignore")


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


def predict(date,code, X_test, platform, pickle_file, model_type, data_type,model,predict_model_type):
    data_dict = {'origin_data': origin_data, 'square_data': square_data, 'log_data': log_data,
                 'radical_data': radical_data, 'cube_data': cube_data}
    model_dict = {'LinearRegression': LinearRegression, 'LogisticRegression': LogisticRegression, 'L1': Lasso,
                  'L2': Ridge,'AE':AE.Autoencoder}

    with open(platform, 'r') as f:
        gene_dict = json.load(f)
        f.close()

    count = 0
    num = len(gene_dict)
    gene_list = []
    print('Now start predict gene...')
    data_test = data_dict[data_type](X_test)
    print("data_test")
    print(data_test)
    if False:
        data_test_pred=None

        gene_data_test=data_test
        # model=LinearRegression(gene_data_test)
        if (model_type == 'AE'):
            hidden_size = 15
            print("gene_data_test.shape")
            print(gene_data_test.shape)
            # model=AE.Autoencoder(in_dim=gene_data_test.shape[1], h_dim=hidden_size)
            model = torch.load('network.pth')  # load network from parameters saved in network.pth @ 22-2-18
            # images = AE.to_var(gene_data_test.T.view(gene_data_test.T.size(0), -1))
            # images = images.float()
            #gene_data_test = torch.from_numpy(gene_data_test)
            gene_data_test = AE.to_var(gene_data_test.view(gene_data_test.size(0), -1))
            gene_data_test = gene_data_test.float()
            out = model(gene_data_test)
            out = out.view(out.size(0), -1)
            pred2 = out.detach().numpy()

        else:
            pred2 = model.predict(gene_data_test.T)

        if count == 1:
            data_test_pred = pred2.T
        else:
            print("data_test_pred")
            print(data_test_pred)
            print("pred2.T")
            print(pred2.T)
            data_test_pred = np.vstack([data_test_pred, pred2.T])
        print('finish!')

    gene_data_test = []
    if True:
        with open(pickle_file, 'rb') as f:
            while True:
                try:
                    count += 1
                    temp = pickle.load(f)
                    gene = temp[0]
                    if(model_type!='AE'):
                        gene_data_test = []
                    for residue in data_test.index:
                        if residue in gene_dict[gene]:
                            gene_data_test.append(data_test.loc[residue])
                    if (model_type != 'AE'):
                        gene_data_test = np.array(gene_data_test)
                    gene_list.append(gene)
                    #print("gene_data_test")
                    #print(gene_data_test)
                    #print("gene_list")
                    #print(gene_list)
                    # print('Now predicting ' + gene + "\tusing " + model_type + "\ton " + data_type + "\t" + str(int(count * 100 / num)) + '% ...')
                    model = temp[1] # deleted

                    #model=LinearRegression(gene_data_test)
                    if(model_type=='AE'):
                        pass
                    else:
                        pred2 = model.predict(gene_data_test.T)
                        if count == 1:
                            data_test_pred = pred2.T
                        else:
                            print("data_test_pred")
                            print(data_test_pred)
                            print("pred2.T")
                            print(pred2.T)
                            data_test_pred = np.vstack([data_test_pred, pred2.T])
                        print('finish!')


################################################################################
                except EOFError:
                    break
        if(model_type=='AE') :
            gene_data_test = np.array(gene_data_test)
            hidden_size = 15
            print("gene_data_test.shape")
            print(gene_data_test.shape)
            model_ae=torch.load(date+'_auto-encoder.pth')
            # model=AE.Autoencoder(in_dim=gene_data_test.shape[1], h_dim=hidden_size)
            model_nn = torch.load(date+'_fully-connected-network.pth')  # load network from parameters saved in network.pth @ 22-2-18
            # images = AE.to_var(gene_data_test.T.view(gene_data_test.T.size(0), -1))
            # images = images.float()
            gene_data_test = torch.from_numpy(gene_data_test)
            gene_data_test = AE.to_var(gene_data_test.view(gene_data_test.size(0), -1))
            gene_data_test = gene_data_test.float()
            embedding = model_ae.code(gene_data_test.T)
            print("predicting:after ae, embedding is ")
            print(embedding)
            print(embedding.shape)
            out = model_nn(embedding)
            out = out.view(out.size(0), -1)
            data_test_pred = out.detach().numpy()
            #print('Now predicting ' + gene + "\tusing " + model_type + "\ton " + data_type + "\t" + str(int(count * 100 / num)) + '% ...')

            '''if count == 1:
                data_test_pred = pred2.T
            else:
                print("data_test_pred")
                print(data_test_pred)
                print("pred2.T")
                print(pred2.T)
                data_test_pred = np.vstack([data_test_pred, pred2.T])'''
            print('finish!')

    data_test_pred = pd.DataFrame(np.array(data_test_pred))
    data_test_pred.to_csv(date+"_"+code + "_gene_level" + "(" + data_type + '_' + model_type + ").txt", sep='\t')
    print("Predicting finish!")


if __name__ == '__main__':
    # Parameter description：
    # code: dataSet ID such as GSE66695 ( string )
    # test_file: test file name( .txt )
    # platform: Gene correspond to methylation characteristics( json file )
    # pickle_file: Parameters of regression model( pickle file )
    # model_type: type of regression model ( string )
    # data_type: type of data ( string )

    # example
    code = "GSE66695"
    test_file = "data_test.txt"
    platform = "platform.json"
    pickle_file = "GSE66695_LinearRegression_origin_datatrain_model.pickle"
    model_type = "LinearRegression"
    data_type = "origin_data"

    test_data = pd.read_table(test_file, index_col=0)

    predict(code,test_data,platform,pickle_file,model_type, data_type)