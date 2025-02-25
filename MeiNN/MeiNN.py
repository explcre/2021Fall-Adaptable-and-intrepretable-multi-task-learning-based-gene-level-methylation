# Copyright (C) 2022 Pengcheng Xu

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
This module contains the main code for generating and fitting a class-aware variational autoencoder.

"""
import tensorflow as tf
# tf.compat.v1.disable_eager_execution()#newly-added-3-27
import json
import os
import sys
import argparse

# import MeiNN.utils as cutils
#from keras.utils.multi_gpu_utils import multi_gpu_model # commented for version reason
from keras.utils.vis_utils import plot_model

import MeiNN.utils as cutils
import math
import numpy as np
import pandas as pd
from keras import backend as K
from keras import callbacks
from keras import layers
from keras import losses
from keras import regularizers
from keras.layers import Dense, Input
from keras.models import Model, model_from_json, load_model
# from keras.utils import plot_model, multi_gpu_model, normalize # not support 22-3-28
from keras.applications.vgg19 import VGG19
from keras.activations import relu
import h5py

from sklearn.metrics import calinski_harabasz_score
from keras import constraints
import matplotlib.pyplot as plt
import textwrap

def _sampling_function(args):
    """
    Utility function to calculate z from the mean and log variance of a normal distribution and mask irrelevant entries.

    :param args: List of z_mean, z_log_var, and mask layers
    :return: z layer
    """
    z_mean, z_log_var, mask = args
    # assert K.shape(z_mean) == K.shape(z_log_var) == K.shape(mask), print('Wrong shape of class mask')
    batch = K.shape(z_mean)[0]
    dim = K.int_shape(z_mean)[1]
    epsilon = K.random_normal(shape=(batch, dim))
    return (z_mean + K.exp(0.5 * z_log_var) * epsilon) * mask


class gene_to_residue_or_pathway_info:
    def __init__(self, gene_to_id_map, residue_to_id_map, gene_to_residue_map, count_connection,
                 gene_to_residue_map_reversed, gene_pathway, gene_pathway_reversed):#,gene_to_residue_map_tensor,gene_pathway_tensor):
        self.gene_to_id_map = gene_to_id_map
        self.residue_to_id_map = residue_to_id_map
        self.gene_to_residue_map = gene_to_residue_map
        self.count_connection = count_connection
        self.gene_to_residue_map_reversed = gene_to_residue_map_reversed
        #self.gene_to_residue_map_tensor=gene_to_residue_map_tensor
        self.gene_pathway = gene_pathway
        self.gene_pathway_reversed = gene_pathway_reversed
        #self.gene_pathway_tensor=gene_pathway_tensor

        self.id_to_gene_map = {v: k for k, v in self.gene_to_id_map.items()}#added
        self.id_to_residue_map = {v: k for k, v in self.residue_to_id_map.items()}#addeds

    def soften(self,to_value,part_option="all"):#part_option: which part? site-gene or gene-pathway or both
        if "site" in part_option or "all" in part_option:
            self.gene_to_residue_map_hard=self.gene_to_residue_map

            self.gene_to_residue_map_softed=self.gene_to_residue_map#=pd.DataFrame(self.gene_to_residue_map).replace(0, to_value)
            for i,row_item in enumerate(self.gene_to_residue_map_softed):
                for j,col_item in enumerate(row_item):
                    if col_item==0:
                        self.gene_to_residue_map_softed[i][j]=to_value
            self.gene_to_residue_map=self.gene_to_residue_map_softed
        if "path" in part_option or "all" in part_option:
            self.gene_pathway_hard=self.gene_pathway
            self.gene_pathway_softed=pd.DataFrame(self.gene_pathway).replace(0, to_value)
            self.gene_pathway=self.gene_pathway_softed

    def mask_info(self,to_value, percentage, count,option="p",part_option="all"):#part_option: which part? site-gene or gene-pathway or both
        self.gene_pathway_masked,self.gene_pathway_masked_position_list=self.random_mask_matrix_ones_to_val(self.gene_pathway, to_value, percentage, count, option)
        self.gene_pathway=self.gene_pathway_masked
        self.gene_to_residue_map_masked,self.gene_to_residue_map_masked_position_list=self.random_mask_matrix_ones_to_val(self.gene_to_residue_map, to_value, percentage, count, option)
        self.gene_to_residue_map=self.gene_to_residue_map_masked


    def sort_pred_matrix(self, pred_matrix, part_option):
        sorted_pred_list = []
        sorted_weight_list = []
        combined_list = []

        if part_option == "path":
            pred_matrix_df = pd.DataFrame(pred_matrix.cpu().detach().numpy(), index=self.gene_pathway.index, columns=self.gene_pathway.columns)
            sorted_indices = np.argsort(pred_matrix_df.values, axis=None)
            sorted_rows, sorted_cols = np.unravel_index(sorted_indices, pred_matrix_df.shape)
            sorted_weight_list = pred_matrix_df.values.ravel()[sorted_indices]

            for i, j in zip(sorted_rows, sorted_cols):
                gene_name = pred_matrix_df.index[i]
                pathway_name = pred_matrix_df.columns[j]
                weight_value = sorted_weight_list[len(sorted_pred_list)]
                sorted_pred_list.append((gene_name, pathway_name))
                combined_list.append((gene_name, pathway_name, weight_value))

        elif part_option == "site":
            sorted_indices = np.argsort(pred_matrix.cpu().detach().numpy(), axis=None)
            sorted_rows, sorted_cols = np.unravel_index(sorted_indices, pred_matrix.shape)
            sorted_weight_list = pred_matrix.cpu().detach().numpy().ravel()[sorted_indices]

            for i, j in zip(sorted_rows, sorted_cols):
                gene_id, residue_id = i, j
                gene_name = self.id_to_gene_map[gene_id]
                residue_name = self.id_to_residue_map[residue_id]
                weight_value = sorted_weight_list[len(sorted_pred_list)]
                sorted_pred_list.append((gene_name, residue_name))
                combined_list.append((gene_name, residue_name, weight_value))

        return sorted_pred_list, sorted_weight_list, combined_list



    def evaluate_weight_site_pathway(self,ae,message):
        
        (pathway_learned_percentile_list, 
            pathway_average_learned_percentile, 
            pathway_all_weights, pathway_ones_distribution, 
            pathway_zeros_distribution, pathway_masked_distribution) = self.evaluate_weight(ae.decoder1[0].weight.T, 0.05, part_option="path", data_name=message)#date+"final"
        if "final" in message:
            print("pathway_learned_percentile_list:", pathway_learned_percentile_list)
            print("pathway_average_learned_percentile:", pathway_average_learned_percentile)
            print("pathway_all_weights:", pathway_all_weights)
            print("pathway_ones_distribution:", pathway_ones_distribution)
            print("pathway_zeros_distribution:", pathway_zeros_distribution)
            print("pathway_masked_distribution:", pathway_masked_distribution)

        (site_learned_percentile_list, 
            site_average_learned_percentile,
            site_all_weights, site_ones_distribution, 
            site_zeros_distribution, site_masked_distribution) = self.evaluate_weight(ae.decoder2[0].weight.T, 0.05, part_option="site", data_name=message)#date+"final"
        if "final" in message:
            print("site_learned_percentile_list:", site_learned_percentile_list)
            print("site_average_learned_percentile:", site_average_learned_percentile)
            print("site_all_weights:", site_all_weights)
            print("site_ones_distribution:", site_ones_distribution)
            print("site_zeros_distribution:", site_zeros_distribution)
            print("site_masked_distribution:", site_masked_distribution)

        if "final" in message:
            sorted_gene_pathway_pairs, sorted_gene_pathway_weight_list, gene_pathway_combined_list = self.sort_pred_matrix(ae.decoder1[0].weight.T, part_option="path")
            self.sorted_gene_pathway_pair_list = sorted_gene_pathway_pairs
            print("Sorted gene-pathway pairs:", sorted_gene_pathway_pairs)

            sorted_gene_residue_pairs, sorted_gene_residue_weight_list, gene_residue_combined_list = self.sort_pred_matrix(ae.decoder2[0].weight.T, part_option="site")
            self.sorted_gene_residue_pair_list = sorted_gene_residue_pairs
            print("Sorted gene-residue pairs:", sorted_gene_residue_pairs)

            # Save sorted_gene_pathway_pair_list to CSV
            sorted_gene_pathway_df = pd.DataFrame(sorted_gene_pathway_pairs, columns=['Pathway', 'Gene'])
            sorted_gene_pathway_df.to_csv(f'sorted_gene_pathway_pairs_{message}.csv', index=False)
            print(f"Saved sorted_gene_pathway_pairs_{message}.csv")

            # Save sorted_gene_pathway_weight_list to CSV
            sorted_gene_pathway_weight_df = pd.DataFrame(sorted_gene_pathway_weight_list, columns=['Weight'])
            sorted_gene_pathway_weight_df.to_csv(f'sorted_gene_pathway_weight_list_{message}.csv', index=False)
            print(f"Saved sorted_gene_pathway_weight_list_{message}.csv")

            # Save gene_pathway_combined_list to CSV
            gene_pathway_combined_df = pd.DataFrame(gene_pathway_combined_list, columns=['Pathway', 'Gene', 'Weight'])
            gene_pathway_combined_df.to_csv(f'gene_pathway_combined_list_{message}.csv', index=False)
            print(f"Saved gene_pathway_combined_list_{message}.csv")

            # Save sorted_gene_residue_pair_list to CSV
            sorted_gene_residue_df = pd.DataFrame(sorted_gene_residue_pairs, columns=['Residue', 'Gene'])
            sorted_gene_residue_df.to_csv(f'sorted_gene_residue_pairs_{message}.csv', index=False)
            print(f"Saved sorted_gene_residue_pairs_{message}.csv")

            # Save sorted_gene_residue_weight_list to CSV
            sorted_gene_residue_weight_df = pd.DataFrame(sorted_gene_residue_weight_list, columns=['Weight'])
            sorted_gene_residue_weight_df.to_csv(f'sorted_gene_residue_weight_list_{message}.csv', index=False)
            print(f"Saved sorted_gene_residue_weight_list_{message}.csv")

            # Save gene_residue_combined_list to CSV
            gene_residue_combined_df = pd.DataFrame(gene_residue_combined_list, columns=['Residue', 'Gene', 'Weight'])
            gene_residue_combined_df.to_csv(f'gene_residue_combined_list_{message}.csv', index=False)
            print(f"Saved gene_residue_combined_list_{message}.csv")


        

    def evaluate_weight(self, pred_matrix,threshold,part_option="path",data_name=""):
        if part_option=="path":
            (learned_percentile_list, 
                average_learned_percentile, 
                all_weights, 
                ones_distribution, 
                zeros_distribution, 
                masked_distribution)=self.evaluate_accuracy_predict_random_mask_matrix_ones(pred_matrix, self.gene_pathway_hard, self.gene_pathway, self.gene_pathway_masked_position_list, threshold,part_option+data_name)

            return (learned_percentile_list, 
                average_learned_percentile, 
                all_weights, 
                ones_distribution, 
                zeros_distribution, 
                masked_distribution)
        if part_option=="site":
            (learned_percentile_list, 
                average_learned_percentile, 
                all_weights, 
                ones_distribution, 
                zeros_distribution, 
                masked_distribution)=self.evaluate_accuracy_predict_random_mask_matrix_ones(pred_matrix, self.gene_to_residue_map_hard, self.gene_to_residue_map, self.gene_to_residue_map_masked_position_list, threshold,part_option+data_name)
            return (learned_percentile_list, 
                average_learned_percentile, 
                all_weights, 
                ones_distribution, 
                zeros_distribution, 
                masked_distribution)
    
    def random_mask_matrix_ones_to_val(self,matrix, to_value, percentage, count, option=""):
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
        toDebug=False
        masked_matrix = matrix.copy()
        if (isinstance(matrix,list)):
            print("it's list , convert to dataframe first")
            masked_matrix=pd.DataFrame(masked_matrix)
        ones_positions = np.argwhere(masked_matrix.to_numpy() == 1)
        if toDebug:
            print("ones_potitions=",ones_positions)
            print("len ones_potitions=",len(ones_positions))
        masked_positions = []
        
        if option == "p":
            count = int(len(ones_positions) * percentage)

        elif option == "c":
            assert count <= len(ones_positions), "Count must be less or equal to the total number of 1s in the matrix."
        print("count of mask position=",count)
        np.random.shuffle(ones_positions)
        if toDebug:
            print("shuffled ones_potitions=",ones_positions)
        for i in range(count):
            masked_positions.append(ones_positions[i].tolist())
            masked_matrix.iat[masked_positions[-1][0], masked_positions[-1][1]] = to_value
        
        if (isinstance(matrix,list)):
            if toDebug:
                print("dataframe masked matrix=")
                print(masked_matrix)
            masked_matrix=masked_matrix.values.tolist()
        return masked_matrix, masked_positions
    
    def wrap_title(self,title, width=50):
        return "\n".join(textwrap.wrap(title, width=width))

    
    def evaluate_accuracy_predict_random_mask_matrix_ones(self, pred_matrix, true_matrix, masked_matrix, masked_position_list, threshold, data_name):
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
        if (isinstance(true_matrix,list)):
            print("true_matrix is list , convert to dataframe first")
            true_matrix=pd.DataFrame(true_matrix)
        if (isinstance(masked_matrix,list)):
            print("masked matrixis list , convert to dataframe first")
            masked_matrix=pd.DataFrame(masked_matrix)
        pred_matrix=pd.DataFrame(pred_matrix.cpu().detach().numpy())

        zero_positions = np.argwhere(true_matrix.to_numpy() == 0)
        masked_positions_values = np.array([pred_matrix.iat[row, col] for row, col in masked_position_list])
        zero_positions_values = np.array([pred_matrix.iat[row, col] for row, col in zero_positions])

        sorted_zero_positions_values = np.sort(zero_positions_values)
        learned_percentile_list = [(np.searchsorted(sorted_zero_positions_values, value) + 1) / len(sorted_zero_positions_values) * 100 for value in masked_positions_values]
         # Sort the learned_percentile_list
        learned_percentile_list.sort()#added
        average_learned_percentile = np.mean(learned_percentile_list)

        all_weights = pred_matrix.values.flatten()
        one_positions = np.argwhere(true_matrix.to_numpy() == 1)
        zero_positions = np.argwhere(true_matrix.to_numpy() == 0)

        ones_distribution = np.array([pred_matrix.iat[row, col] for row, col in one_positions])
        zeros_distribution = np.array([pred_matrix.iat[row, col] for row, col in zero_positions])
        masked_distribution = np.array([pred_matrix.iat[row, col] for row, col in masked_position_list])
        # Non-zero distribution
        non_one_positions = np.argwhere(true_matrix.to_numpy() != 1)
        non_one_distribution = np.array([pred_matrix.iat[row, col] for row, col in non_one_positions])

        
        
        # Calculate the number of bins
        matrix_shape = pred_matrix.shape
        total_elements = matrix_shape[0] * matrix_shape[1]
        num_bins = int(np.sqrt(total_elements))
        funciton_name="eval_mask"
        # Save plots
        plt.clf() # clear figure
        plt.cla() # clear axis
        plt.close() # close window

        plt.hist(all_weights, bins=num_bins)
        plt.xlabel('Weight')
        plt.ylabel('Frequency')
        plt.title(self.wrap_title('All Weights Distribution ({data_name})'))
        plt.savefig(f'{funciton_name}_{data_name}_all_weights_distribution.png')
        plt.clf()

        plt.hist(ones_distribution, bins=num_bins)
        plt.xlabel('Weight')
        plt.ylabel('Frequency')
        plt.title(self.wrap_title('Ones Distribution ({data_name})'))
        plt.savefig(f'{funciton_name}_{data_name}_ones_distribution.png')
        plt.clf()

        plt.hist(zeros_distribution, bins=num_bins)
        plt.xlabel('Weight')
        plt.ylabel('Frequency')
        plt.title(self.wrap_title('Zeros Distribution ({data_name})'))
        plt.savefig(f'{funciton_name}_{data_name}_zeros_distribution.png')
        plt.clf()

        plt.hist(masked_distribution, bins=num_bins)
        plt.xlabel('Weight')
        plt.ylabel('Frequency')
        plt.title(self.wrap_title('Masked Distribution ({data_name})'))
        plt.savefig(f'{funciton_name}_{data_name}_masked_distribution.png')
        plt.clf()
        '''
        plt.bar(range(len(learned_percentile_list)), learned_percentile_list)
        plt.xlabel('Position Index')
        plt.ylabel('Learned Percentile')
        plt.title('Learned Percentile List')
        plt.savefig(f'{funciton_name}_{data_name}_learned_percentile_list.png')
        plt.clf()'''
        
        plt.hist(non_one_distribution, bins=num_bins)
        plt.xlabel('Weight')
        plt.ylabel('Frequency')
        plt.title(self.wrap_title(f'Non-One Weights Distribution ({data_name})'))
        plt.savefig(f'{funciton_name}_{data_name}_non_one_distribution.png')
        plt.clf()

        plt.hist(masked_distribution, bins=num_bins, alpha=0.5, label='Masked Distribution', color='blue')
        plt.hist(non_one_distribution, bins=num_bins, alpha=0.5, label='Non-One Distribution', color='red')
        plt.xlabel('Weight')
        plt.ylabel('Frequency')
        plt.legend(loc='upper right')
        plt.title(self.wrap_title(f'Masked and Non-One Weights Distribution ({data_name})'))
        plt.savefig(f'{funciton_name}_{data_name}_masked_and_non_one_distribution.png')
        plt.clf()

        plt.bar(range(len(learned_percentile_list)), learned_percentile_list)
        plt.xlabel('Position Index (Sorted)')
        plt.ylabel('Learned Percentile')
        plt.title(self.wrap_title(f'Learned Percentile List (Avg: {average_learned_percentile:.2f}%) ({data_name})'))
        plt.savefig(f'{funciton_name}_{data_name}_learned_percentile_list.png')
        plt.clf()

        return (learned_percentile_list, 
            average_learned_percentile, 
            all_weights, 
            ones_distribution, 
            zeros_distribution, 
            masked_distribution)




class MeiNN:
    """Main class for the MeiNN architecture.

    """

    def __init__(self, config, path, date, code, X_train, y_train, platform, model_type, data_type,
                 HIDDEN_DIMENSION, toTrainMeiNN, AE_epoch_from_main=1000, NN_epoch_from_main=1000,
                 separatelyTrainAE_NN=True,
                 model_dir='./saved_model/',
                 train_dataset_filename=r"./dataset/data_train.txt", train_label_filename=r"./dataset/label_train.txt",
                 gene_to_site_dir=r"./platform.json", gene_to_residue_or_pathway_info=None,
                 toAddGeneSite=True, toAddGenePathway=True,
                 multiDatasetMode="softmax", datasetNameList=[], lossMode='reg_mean'):
        """

        :param model_dir: Directory to save training weights and log files
        :param config: Config class containing parameters for resVAE
        """
        # assert os.path.isdir(model_dir)# | model_dir is None
        self.outputSet = []
        # self.modelSet=[]
        self.model_dir = model_dir
        self.config = config
        self.built = False
        self.compiled = False
        self.isfit = False
        self.l_rate = K.variable(0.01)
        self.genes = None
        self.classes = None
        self.dot_weights = 0
        self.gpu_count = K.tensorflow_backend._get_available_gpus()
        # self.gpu_count = tf.config.list_physical_devices('GPU')
        self.x_train = X_train  # pd.read_table(train_dataset_filename,index_col=0)
        self.y_train = y_train  # pd.read_table(train_label_filename, index_col=0).values.ravel()
        self.NN_epoch_from_main = NN_epoch_from_main
        self.AE_epoch_from_main = AE_epoch_from_main
        self.path = path
        self.date = date
        self.code = code
        self.model_type = model_type
        self.data_type = data_type
        self.HIDDEN_DIMENSION = HIDDEN_DIMENSION
        self.gene_to_site_dir = gene_to_site_dir
        self.gene_to_residue_or_pathway_info = gene_to_residue_or_pathway_info
        self.toAddGeneSite = toAddGeneSite
        self.toAddGenePathway = toAddGenePathway
        self.multiDatasetMode = multiDatasetMode
        self.datasetNameList = datasetNameList
        self.lossMode = lossMode
        self.separatelyTrainAE_NN = separatelyTrainAE_NN
        self.autoencoder, self.encoder, self.fcn, self.pred_nn, self.embedding, self.embedding2pred_nn,self.fcn_multitask= self.build()

    def build(self, update: bool = False):
        """
        Function that constructs the resVAE architecture, including both the encoder and decoder parts.

        :return: returns the encoder, decoder, and complete resVAE keras models
        """

        if not update:
            assert not self.built, print('Model is already built and update is set to False')
        input_shape, latent_dim = self.config['INPUT_SHAPE']
        encoder_shape = self.config['ENCODER_SHAPE']
        decoder_shape = self.config['DECODER_SHAPE']
        activ = self.config['ACTIVATION']
        last_activ = self.config['LAST_ACTIVATION']
        dropout = self.config['DROPOUT']
        latent_scale = self.config['LATENT_SCALE']
        latent_offset = self.config['LATENT_OFFSET']
        decoder_bias = self.config['DECODER_BIAS']
        decoder_regularizer = self.config['DECODER_REGULARIZER']
        decoder_regularizer_initial = self.config['DECODER_REGULARIZER_INITIAL']
        base_loss = self.config['BASE_LOSS']
        decoder_bn = self.config['DECODER_BN']
        relu_thresh = self.config['DECODER_RELU_THRESH']
        assert activ in ['relu', 'elu'], print('invalid activation function')
        assert last_activ in ['sigmoid', 'softmax', 'relu', None], print('invalid final activation function')
        assert decoder_bias in ['all', 'none', 'last']
        assert decoder_regularizer in ['var_l1', 'var_l2', 'var_l1_l2',
                                       'l1', 'l2', 'l1_l2', 'dot', 'dot_weights', 'none']
        assert base_loss in ['mse', 'mae']

        #######################################################################
        # --2022-3-28 Pengcheng Xu

        latent_dim = self.gene_to_residue_or_pathway_info.gene_pathway.shape[0]  # self.HIDDEN_DIMENSION
        print("INFO: latentdim=%d" % latent_dim)
        decoder_regularizer = 'var_l1'
        decoder_regularizer_initial = 0.0001
        activ = 'relu'
        latent_scale = 5
        l_rate = K.variable(0.01)
        relu_thresh = 0
        decoder_bn = False
        decoder_bias = 'last'
        last_activ = 'tanh'  # 'softmax'
        gene_layer_dim = len(self.gene_to_residue_or_pathway_info.gene_to_id_map)
        residue_layer_dim = len(self.gene_to_residue_or_pathway_info.residue_to_id_map)

        in_dim = residue_layer_dim  # int(809)#modified 2022-4-14
        print("residue_layer_dim=")
        print(residue_layer_dim)
        print("gene_layer_dim=")
        print(gene_layer_dim)
        # Compress the dimension to latent_dim
        mid_dim = int(math.sqrt(in_dim * latent_dim))
        q3_dim = int(math.sqrt(in_dim * mid_dim))
        q1_dim = int(math.sqrt(latent_dim * mid_dim))
        # decoder_shape = [latent_dim, q1_dim, mid_dim, q3_dim]
        encoder_shape = [gene_layer_dim, residue_layer_dim, latent_dim]
        decoder_shape = [latent_dim, gene_layer_dim]  # modified on 2022-4-14 #, residue_layer_dim]
        input_shape = (residue_layer_dim)

        if decoder_regularizer == 'dot_weights':
            dot_weights = np.zeros(shape=(latent_scale * latent_dim, latent_scale * latent_dim))
            for s in range(latent_dim):
                dot_weights[s * latent_scale:s * latent_scale + latent_scale,
                s * latent_scale:s * latent_scale + latent_scale] = 1

        # L1 regularizer with the scaling factor updateable through the l_rate variable (callback)
        def variable_l1(x):
            return l_rate * K.sum(K.abs(x))

        class MyRegularizer_variable_l1(regularizers.Regularizer):

            def __init__(self, l_rate=K.variable(0.01)):
                self.l_rate = l_rate

            def __call__(self, x):
                return self.l_rate * sum(abs(x))

            def get_config(self):
                return {'l_rate': self.l_rate}

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
            reg1 = dotprod_weights  # originally
            reg = dotprod
        else:
            reg = None
            reg1 = None

        # this is our input placeholder
        input = layers.Input(shape=(in_dim,))
        # 编码层
        encoded = layers.Dense(q3_dim, activation='relu')(input)
        encoded = layers.Dense(mid_dim, activation='relu')(encoded)
        encoded = layers.Dense(q1_dim, activation='relu')(encoded)
        encoder_output = layers.Dense(latent_dim, name="input_to_encoding")(encoded)
        decoded0 = encoder_output
        '''
        decoded = layers.Dense(latent_dim,
                               activation=activ,
                               name='Decoder1',
                               activity_regularizer='l1')(encoder_output)'''
        # activity_regularizer=reg1 # originally
        if decoder_bn:
            decoded = layers.BatchNormalization()(decoded0)
        # adds layers to the decoder. See encoder layers
        if len(decoder_shape) > 1:
            for i in range(len(decoder_shape) - 1):
                if decoder_bias == 'all':
                    decoded = layers.Dense(decoder_shape[i + 1],
                                           activation=activ,
                                           name='Dense_D' + str(i + 2),
                                           use_bias=True,
                                           activity_regularizer='l1')(decoded0)
                else:
                    decoded = layers.Dense(decoder_shape[i + 1],
                                           activation=activ,
                                           name='Dense_D' + str(i + 2),
                                           use_bias=False,
                                           kernel_regularizer='l1')(decoded0)
                if decoder_bn:
                    decoded = layers.BatchNormalization()(decoded)

        # kernel_regularizer=reg # originally

        if decoder_bias == 'none':
            self.ae_outputs = layers.Dense(input_shape,
                                           activation=last_activ,
                                           use_bias=False, name='ae_output')(decoded)
        else:
            self.ae_outputs = layers.Dense(input_shape,
                                           activation=last_activ, name='ae_output')(decoded)

        # 解码层
        # decoded = Dense(q1_dim, activation='relu')(encoder_output)
        # decoded = Dense(mid_dim, activation='relu')(decoded)
        # decoded = Dense(q3_dim, activation='relu')(decoded)
        # decoded = Dense(in_dim, activation='tanh')(decoded)

        ###############################################################
        # 构建自编码模型
        self.autoencoder = Model(inputs=input, outputs=self.ae_outputs)

        # 构建编码模型
        self.encoder = Model(inputs=input, outputs=encoder_output)

        # compile autoencoder
        self.autoencoder.compile(optimizer='adam', loss='binary_crossentropy')  # loss='mse'
        ################################################################

        self.input_to_encoding_model = Model(inputs=self.autoencoder.input,
                                             outputs=self.autoencoder.get_layer('input_to_encoding').output)

        print("input_to_encoding_model.predict(gene_data_train.T)")
        print(self.input_to_encoding_model.predict(self.x_train))
        # embedding=ae.code(torch.tensor(gene_data_train.T).float())
        self.embedding = self.input_to_encoding_model.predict(self.x_train)
        embedding_df = pd.DataFrame(self.embedding)
        # self.path="./result/"
        # "C:/Users/xupengch/Downloads/methylation/2020Fall-Adaptable-and-intrepretable-multi-task-learning-based-gene-level-methylation-estimation-main"
        # +self.path +
        embedding_df.to_csv(
            self.path + self.date + "_" + self.code + "_gene_level" + "(" + self.data_type + '_' + self.model_type + "_embedding_original).txt",
            sep='\t')

        print("embedding is ")
        print(self.embedding)
        print(self.embedding.shape)

        in_dim = latent_dim
        # output dimension is 1
        out_dim = len(self.datasetNameList)

        mid_dim = int(math.sqrt(in_dim * latent_dim))
        q3_dim = int(math.sqrt(in_dim * mid_dim))

        q1_dim = int(math.sqrt(latent_dim * mid_dim))
        # this is our input placeholder

        # input = Input(shape=(in_dim,))
        # 编码层
        out_x = Dense(q3_dim, name='after_embedding_layer1', activation='relu')(encoder_output)
        out_x = Dense(mid_dim, activation='relu')(out_x)
        out_x = Dense(q1_dim, activation='relu')(out_x)
        self.output = Dense(out_dim, activation='sigmoid', name="prediction")(out_x)  # originally sigmoid

        def reconstruct_and_predict_loss(x, ae_outputs, output, y_train, y_index):
            reconstruct_loss = losses.binary_crossentropy(x, ae_outputs)
            print(output[0])
            print("y_train.T=")
            print(y_train.T)
            print("y_train.T.shape=")
            print(y_train.T.shape)
            predict_loss = losses.binary_crossentropy(y_pred=output, y_true=y_train.T[
                y_index])  # - 0.5 * K.mean(1 + z_log_sigma - K.square(z_mean) - K.exp(z_log_sigma), axis=-1)
            return K.mean(reconstruct_loss + predict_loss)

        def my_reconstruct_and_predict_loss(y_true, y_pred, lam=0.5):
            reconstruct_loss = losses.binary_crossentropy(y_true=self.x_train,
                                                          y_pred=self.autoencoder.get_layer('ae_output').output)
            predict_loss = losses.binary_crossentropy(y_true,
                                                      y_pred)  # - 0.5 * K.mean(1 + z_log_sigma - K.square(z_mean) - K.exp(z_log_sigma), axis=-1)
            return K.mean(lam * reconstruct_loss + (1 - lam) * predict_loss)

        reconstruct_loss = losses.binary_crossentropy(input, self.ae_outputs)
        # predict_loss = losses.binary_crossentropy(y_true,y_pred)
        print(
            "in MeiNNself.reconstruct_and_predict_loss=my_reconstruct_and_predict_loss(y_true=self.y_train[0],y_pred=self.output[0])")
        print("y_true=self.y_train[0]     y_train=")
        print(self.y_train)
        # print("self.y_train[0]=")
        # print(self.y_train[0])
        # print("y_pred=self.output[0]     output=")
        # print(self.output)
        # print("self.output[0]")
        # print(self.output[0])
        # self.reconstruct_and_predict_loss=my_reconstruct_and_predict_loss(y_true=self.y_train[0],y_pred=self.output[0])#K.mean(reconstruct_loss + predict_loss)

        # build the fcn model
        self.fcn = Model(inputs=[input], outputs=[self.ae_outputs, self.output])
        print(self.fcn.summary())
        # build prediction nn
        self.pred_nn = Model(inputs=input, outputs=self.output)
        # print(self.pred_nn.summary())
        # self.pred_nn.compile(optimizer='adam', loss='binary_crossentropy')

        # self.fcn.compile(optimizer=optimizer, loss='binary_crossentropy')
        # build embedding to pred
        input_embedding2pred_nn = layers.Input(shape=(latent_dim,))
        out_x = Dense(q3_dim, name='after_embedding_layer1', activation='relu')(input_embedding2pred_nn)
        out_x = Dense(mid_dim, activation='relu')(out_x)
        out_x = Dense(q1_dim, activation='relu')(out_x)
        self.output_embedding2pred_nn = Dense(out_dim, activation='sigmoid', name="prediction")(out_x)
        self.embedding2pred_nn = Model(inputs=input_embedding2pred_nn,
                                       outputs=self.output_embedding2pred_nn)  # Model(inputs=self.pred_nn.get_layer('after_embedding_layer1').input,

        #####################added 5-30 for predict nn and multi-task nn #
        if self.multiDatasetMode == 'multi-task':
            for i in range(len(self.datasetNameList)):
                out_x = Dense(q3_dim, name='after_embedding_layer1%d' % i, activation='relu')(encoder_output)
                out_x = Dense(mid_dim, activation='relu')(out_x)
                out_x = Dense(q1_dim, activation='relu')(out_x)
                multi_task_output = Dense(1, activation='sigmoid', name="prediction%d" % i)(out_x)
                self.outputSet.append(multi_task_output)
            if len(self.datasetNameList) == 6:
                self.fcn_multitask = Model(inputs=[input],
                                           outputs=[self.ae_outputs, self.outputSet[0], self.outputSet[1],
                                                    self.outputSet[2], self.outputSet[3], self.outputSet[4],
                                                    self.outputSet[5]])
                print("self.fcn_multitask.summary()")
                print(self.fcn_multitask.summary())
                # self.modelset[i]=tasknn_i

        # outputs=self.pred_nn.get_layer('prediction').output)
        # compile fcn
        # self.fcn.compile(optimizer='adam', loss=reconstruct_and_predict_loss,
        #          experimental_run_tf_function=False)  # loss='mse'#'binary_crossentropy'

        '''
        # training
        # fcn.fit(embedding, y_train.T, epochs=NN_epoch_from_main, batch_size=79, shuffle=True)
        fcn.fit(gene_data_train.T, y_train.T, epochs=NN_epoch_from_main, batch_size=79, shuffle=True)
        print("FCN finish_fitting")
        fcn.save(path + date + 'FCN.h5')
        print("FCN finish saving model")

        embedding = input_to_encoding_model.predict(
            gene_data_train.T)  # input_to_encoding_model.predict(gene_data_train.T)
        embedding_df = pd.DataFrame(embedding)
        embedding_df.to_csv(
            path + date + "_" + code + "_gene_level" + "(" + data_type + '_' + model_type + "_embedding_trained).txt",
            sep='\t')

        print("embedding is ")
        print(embedding)
        print(embedding.shape)
        '''

        #######################################################################

        # set built to true to later avoid inadvertently overwriting a built model. TODO: implement this check
        self.built = True
        return self.autoencoder, self.encoder, self.fcn, self.pred_nn, self.embedding, self.embedding2pred_nn,self.fcn_multitask

    def loss(self, y_true=None, y_pred=None):
        return self.reconstruct_and_predict_loss

    def compile(self):
        """
        This function compiles the keras model of the complete resVAE network.

        :return: None
        """
        # TODO: Add metrics
        '''
        if self.config['MULTI_GPU'] == True:
            self.autoencoder = multi_gpu_model(model=self.autoencoder, gpus=len(self.gpu_count))
            self.encoder = multi_gpu_model(model=self.encoder, gpus=len(self.gpu_count))
            self.decoder = multi_gpu_model(model=self.decoder, gpus=len(self.gpu_count))
            self.fcn = multi_gpu_model(model=self.fcn, gpus=len(self.gpu_count))
        elif type(self.config['MULTI_GPU']) == int:
            assert self.config['MULTI_GPU'] > 0, print('Please choose an integer larger than 0 for the GPU count.')
            assert self.config['MULTI_GPU'] <= len(self.gpu_count), \
                print('Number of GPU counts provided ('+ str(self.config['MULTI_GPU'])+') may not exceed available GPU count ('+str(len(self.gpu_count))+').')
            self.autoencoder = multi_gpu_model(model=self.autoencoder, gpus=len(self.gpu_count))
            self.encoder = multi_gpu_model(model=self.encoder, gpus=self.config['MULTI_GPU'])
            self.decoder = multi_gpu_model(model=self.decoder, gpus=self.config['MULTI_GPU'])
            self.resvae_model = multi_gpu_model(model=self.fcn, gpus=self.config['MULTI_GPU'])

        '''

        def explainableAELoss(y_true, y_pred):
            weight = self.fcn.get_weights()
            ans = losses.binary_crossentropy(y_true, y_pred)
            rate_site = 2.0
            rate_pathway = 2.0
            if self.toAddGeneSite:
                for i in range(len(weight)):
                    print("weight[%d]*******************************************" % i)
                    # print(weight[i])
                    print(weight[i].shape)
                print("self.gene_to_residue_info.gene_to_residue_map.shape")
                print(len(self.gene_to_residue_or_pathway_info.gene_to_residue_map))
                print(len(self.gene_to_residue_or_pathway_info.gene_to_residue_map[0]))

                regular_site = abs(
                    rate_site * weight[15] * self.gene_to_residue_or_pathway_info.gene_to_residue_map_reversed)

                if self.toAddGenePathway:
                    regular_pathway = abs(
                        rate_pathway * weight[12] * self.gene_to_residue_or_pathway_info.gene_pathway_reversed)
                    if self.lossMode == 'reg_mean':
                        ans += np.sum(regular_site) / len(regular_site) + np.sum(regular_pathway) / len(regular_pathway)
                    else:
                        ans += np.sum(regular_site) + np.sum(regular_pathway)
                elif self.lossMode == 'reg_mean':
                    ans += np.sum(regular_site) / len(regular_site)
                else:
                    ans += np.sum(regular_site)  # +1000*np.random.uniform(1)
            elif self.toAddGenePathway:
                regular_pathway = abs(
                    rate_pathway * weight[12] * self.gene_to_residue_or_pathway_info.gene_pathway_reversed)
                if self.lossMode == 'reg_mean':
                    ans += np.sum(regular_pathway) / len(regular_pathway)
                else:
                    ans += np.sum(regular_pathway)
            return ans

        def myLoss(y_true, y_pred):
            weight = self.fcn.get_weights()
            ans = losses.binary_crossentropy(y_true, y_pred)
            rate_site = 2.0
            rate_pathway = 2.0
            if self.toAddGeneSite:
                for i in range(len(weight)):
                    print("weight[%d]*******************************************" % i)
                    # print(weight[i])
                    print(weight[i].shape)
                print("self.gene_to_residue_info.gene_to_residue_map.shape")
                print(len(self.gene_to_residue_or_pathway_info.gene_to_residue_map))
                print(len(self.gene_to_residue_or_pathway_info.gene_to_residue_map[0]))

                regular_site = abs(
                    rate_site * weight[15] * self.gene_to_residue_or_pathway_info.gene_to_residue_map_reversed)

                if self.toAddGenePathway:
                    regular_pathway = abs(
                        rate_pathway * weight[12] * self.gene_to_residue_or_pathway_info.gene_pathway_reversed)
                    if self.lossMode == 'reg_mean':
                        ans += np.sum(regular_site) / len(regular_site) + np.sum(regular_pathway) / len(regular_pathway)
                    else:
                        ans += np.sum(regular_site) + np.sum(regular_pathway)
                elif self.lossMode == 'reg_mean':
                    ans += np.sum(regular_site) / len(regular_site)
                else:
                    ans += np.sum(regular_site)  # +1000*np.random.uniform(1)
            elif self.toAddGenePathway:
                regular_pathway = abs(
                    rate_pathway * weight[12] * self.gene_to_residue_or_pathway_info.gene_pathway_reversed)
                if self.lossMode == 'reg_mean':
                    ans += np.sum(regular_pathway) / len(regular_pathway)
                else:
                    ans += np.sum(regular_pathway)
            return ans

        optimizer = self.config['OPTIMIZER']
        from keras import metrics
        self.autoencoder.compile(optimizer=optimizer, loss=explainableAELoss)
        self.fcn.compile(optimizer=optimizer, loss=[myLoss, losses.binary_crossentropy
                                                    ])  # ,metrics='accuracy')#experimental_run_tf_function=False
        lossList = []
        if self.multiDatasetMode == 'multi-task':
            lossList.append(myLoss)
            for i in range(len(self.datasetNameList)):
                lossList.append(losses.binary_crossentropy)
            if len(self.datasetNameList) == 6:
                self.fcn_multitask.compile(optimizer=optimizer,
                                           loss=[myLoss, losses.binary_crossentropy, losses.binary_crossentropy,
                                                 losses.binary_crossentropy, losses.binary_crossentropy,
                                                 losses.binary_crossentropy,
                                                 losses.binary_crossentropy])

        self.pred_nn.compile(optimizer=optimizer, loss='binary_crossentropy')
        self.embedding2pred_nn.compile(optimizer=optimizer, loss='binary_crossentropy')
        # self.fcn.compile(optimizer=optimizer, loss=[losses.binary_crossentropy(y_true=self.x_train,
        #                                                  y_pred=self.autoencoder.get_layer('ae_output').output),losses.binary_crossentropy(y_true=self.y_train,y_pred=self.output[0])])#experimental_run_tf_function=False
        # self.fcn.compile(optimizer=optimizer, loss=self.reconstruct_and_predict_loss)
        self.compiled = True

    def fit(self, exprs=None, classes=None, model_dir=None, model_name='my_rlvae'):
        """
        Function to fit the complete resVAE model to the provided training data.

        :param exprs: Input matrix (samples x features)
        :param classes: One-hot encoded or partial class identity matrix (samples x classes)
        :param model_dir: Directory to save training logs in
        :param model_name: Na0me of the model (for log files
        :return: Returns a keras history object and a dictionary with scores
        """

        assert self.compiled, print('Please compile the model first by running rlvae.compile()')
        '''
        batch_size = self.config['BATCH_SIZE']
        epochs = self.config['EPOCHS']
        steps_per_epoch = self.config['STEPS_PER_EPOCH']
        validation_split = self.config['VALIDATION_SPLIT']
        callback = []
        if self.config['CB_LR_USE']:
            callback.append(callbacks.ReduceLROnPlateau(monitor=self.config['CB_MONITOR'],
                                                        factor=self.config['CB_LR_FACTOR'],
                                                        patience=self.config['CB_LR_PATIENCE'],
                                                        min_delta=self.config['CB_LR_MIN_DELTA'],
                                                        verbose=True))
        if self.config['CB_ES_USE']:
            callback.append(callbacks.EarlyStopping(monitor=self.config['CB_MONITOR'],
                                                    patience=self.config['CB_ES_PATIENCE'],
                                                    min_delta=self.config['CB_ES_MIN_DELTA'],
                                                    verbose=True))
        if model_dir is not None:
            callback.append(callbacks.CSVLogger(os.path.join(model_dir, str(model_name + '.log'))))
        decoder_regularizer = self.config['DECODER_REGULARIZER']
        decoder_regularizer_initial = self.config['DECODER_REGULARIZER_INITIAL']
        if decoder_regularizer in ['var_l1', 'var_l2', 'var_l1_l2']:
            callback.append(callbacks.LambdaCallback(on_epoch_end=lambda epoch,
                                                      logs: K.set_value(self.l_rate,
                                                                        decoder_regularizer_initial * (epoch + 1))))
        history = self.resvae_model.fit([exprs, classes],
                                        batch_size=batch_size,
                                        epochs=epochs,
                                        steps_per_epoch=steps_per_epoch,
                                        validation_split=validation_split,
                                        callbacks=callback)
        self.isfit = True
        fpc_real = self.calc_fpc()
        scores = {'fpc_real': fpc_real}
        #self.fcn.fit(gene_data_train.T, y_train.T, epochs=NN_epoch_from_main, batch_size=79, shuffle=True)
        self.fcn.fit(self.x_train.T, self.y_train.T, epochs=self.NN_epoch_from_main, batch_size=79, shuffle=True)
        # training
        # fcn.fit(embedding, y_train.T, epochs=NN_epoch_from_main, batch_size=79, shuffle=True)
        '''
        import matplotlib.pyplot as plt
        import keras
        class LossHistory(keras.callbacks.Callback):  # ,path="",date="",code="",data_type='origin'):
            def __init__(self, path, date, code, model_type='AE', data_type='origin'):
                self.path = path
                self.date = date
                self.code = code
                self.model_type = model_type
                self.data_type = data_type

            def on_train_begin(self, logs={}):
                self.losses = {'batch': [], 'epoch': []}
                self.accuracy = {'batch': [], 'epoch': []}
                self.val_loss = {'batch': [], 'epoch': []}
                self.val_acc = {'batch': [], 'epoch': []}

            def on_batch_end(self, batch, logs={}):
                self.losses['batch'].append(logs.get('loss'))
                self.accuracy['batch'].append(logs.get('acc'))
                self.val_loss['batch'].append(logs.get('val_loss'))
                self.val_acc['batch'].append(logs.get('val_acc'))

            def on_epoch_end(self, batch, logs={}):
                self.losses['epoch'].append(logs.get('loss'))
                self.accuracy['epoch'].append(logs.get('acc'))
                self.val_loss['epoch'].append(logs.get('val_loss'))
                self.val_acc['epoch'].append(logs.get('val_acc'))

            def loss_plot(self, loss_type, filename):
                iters = range(len(self.losses[loss_type]))
                fig = plt.figure()
                # acc
                plt.plot(iters, self.accuracy[loss_type], 'r', label='train acc')
                # loss
                plt.plot(iters, self.losses[loss_type], 'g', label='train loss')
                if loss_type == 'epoch':
                    # val_acc
                    plt.plot(iters, self.val_acc[loss_type], 'b', label='val acc')
                    # val_loss
                    plt.plot(iters, self.val_loss[loss_type], 'k', label='val loss')
                plt.grid(True)
                plt.xlabel(loss_type)
                plt.ylabel('acc-loss')
                plt.legend(loc="upper right")
                # plt.show()
                fig.savefig(
                    self.path + self.date + "_" + self.code + "_gene_level" + "(" + self.data_type + '_' + self.model_type + filename + "_loss_epoch).png")

        history = LossHistory(self.path, self.date, self.code)
        if self.separatelyTrainAE_NN:
            self.autoencoder.fit(self.x_train, self.x_train, epochs=self.AE_epoch_from_main,  # batch_size=79,
                                 shuffle=True, callbacks=[history])
            print("AE finish_fitting")
            history.loss_plot('epoch', 'AE')

            self.autoencoder.save(self.path + self.date + 'AE.h5')
            print("AE finish saving model")
            self.embedding = self.input_to_encoding_model.predict(
                self.x_train)  # input_to_encoding_model.predict(gene_data_train.T)
            self.embedding2pred_nn.fit(self.embedding, self.y_train, epochs=self.NN_epoch_from_main,  # batch_size=79,
                                       shuffle=True, callbacks=[history])
            print("embedding2pred_nn finish_fitting")
            history.loss_plot('epoch', 'embedding2pred_nn')

            self.embedding2pred_nn.save(self.path + self.date + 'embedding2pred_nn.h5')
            print("embedding2pred_nn finish saving model")
            '''embedding_df = pd.DataFrame(embedding)
            embedding_df.to_csv(
                self.path + self.date + "_" + self.code + "_gene_level" + "(" + self.data_type + '_' + self.model_type + "_embedding_trained).txt",
                sep='\t')'''

        else:
            if self.multiDatasetMode == 'multi-task':
                print("DEBUG INFO: self.fcn_multitask.summary()):")
                print(self.fcn_multitask.summary())
                outputList = []
                print("DEBUG INFO: in theoutputList:")
                outputList.append(self.x_train)
                print("DEBUG INFO: self.y_train=")
                print(self.y_train)
                for i in range(len(self.datasetNameList)):
                    print("DEBUG INFO: self.y_train%d" % i)
                    print(self.y_train.iloc[:,i])
                    outputList.append(self.y_train.iloc[:,i])
                if len(self.datasetNameList)==6:
                    self.fcn_multitask.fit(self.x_train, [self.x_train,self.y_train.iloc[:,0],self.y_train.iloc[:,1],self.y_train.iloc[:,2],
                                                          self.y_train.iloc[:,3],self.y_train.iloc[:,4],self.y_train.iloc[:,5]], epochs=self.NN_epoch_from_main,
                                       # batch_size=79,
                                       shuffle=True, callbacks=[history])
                print("multi-task MeiNN finish_fitting")
                history.loss_plot('epoch', 'multi task MeiNN')

                self.fcn_multitask.save(self.path + self.date + 'multi-task-MeiNN.h5')
                print("multi-task MeiNN finish saving model")
            else:
                self.fcn.fit(self.x_train, [self.x_train, self.y_train], epochs=self.NN_epoch_from_main,
                             # batch_size=79,
                             shuffle=True, callbacks=[history])
                print("MeiNN finish_fitting")
                history.loss_plot('epoch', 'MeiNN')

                self.fcn.save(self.path + self.date + 'MeiNN.h5')
                print("MeiNN finish saving model")

        embedding = self.input_to_encoding_model.predict(
            self.x_train)  # input_to_encoding_model.predict(gene_data_train.T)
        embedding_df = pd.DataFrame(embedding)
        embedding_df.to_csv(
            self.path + self.date + "_" + self.code + "_gene_level" + "(" + self.data_type + '_' + self.model_type + "_embedding_trained).txt",
            sep='\t')

        print("embedding is ")
        print(embedding)
        print(embedding.shape)

        print("****************InMeiNN*****************************************")
        print("count_gene=%d" % len(self.gene_to_residue_or_pathway_info.gene_to_id_map))
        print("gene_to_id_map:")
        print(self.gene_to_residue_or_pathway_info.gene_to_id_map)
        print("count_residue=%d" % len(self.gene_to_residue_or_pathway_info.residue_to_id_map))
        print("residue_to_id_map:")
        print(self.gene_to_residue_or_pathway_info.residue_to_id_map)
        # print("gene_to_residue_map:")
        # print(gene_to_residue_map)
        print("count_connection=%d" % self.gene_to_residue_or_pathway_info.count_connection)
        # return history, scores
        return

    def smooth(self, exprs, classes):
        """
        This generates smoothed values, i.e. values output by the complete resVAE model.

        :param exprs: Matrix with values to be smoothed (samples x features)
        :param classes: One-hot encoded or partial class identity matrix (samples x classes)
        :return: Smoothed value estimates
        """
        return self.resvae_model.predict([exprs, classes])

    def simulate(self, classes):
        """
        This generates simulated values based on just the decoder part of resVAE.

        :param classes: Input for the latent space (samples x (classes * latent scale factor))
        :return: Simulated values
        """
        return self.decoder.predict(classes)

    def describe_model(self, model: str = 'rlvae', plot=False, filename=None):
        """
        Generates summaries of the model architecture, prints them to stdout and optionally saves them as .png files.

        :param model: Model to show (one value or a list of 'encoder', 'decoder', or 'rlvae')
        :param plot: Boolean indicating whether to plot the model architectures as .png
        :param filename: Filenames for the plots generated. Either a single string or a list with the same length as the model list.
        :return: None
        """
        assert model in ['encoder', 'decoder', 'rlvae'], print('Unknown model identifier')
        model = np.asarray(model)
        if 'encoder' in model:
            print(self.encoder.summary())
            if plot:
                assert filename is not None, print('Please provide a file name for plotting!')
                if type(filename) == list:
                    plot_model(self.encoder, to_file=filename[np.where(model == 'encoder')[0]])
                else:
                    plot_model(self.encoder, to_file=filename)
        if 'decoder' in model:
            print(self.decoder.summary())
            if plot:
                assert filename is not None, print('Please provide a file name for plotting!')
                if type(filename) == list:
                    plot_model(self.decoder, to_file=filename[np.where(model == 'decoder')[0]])
                else:
                    plot_model(self.decoder, to_file=filename)
        if 'resvae' in model:
            print(self.resvae_model.summary())
            if plot:
                assert filename is not None, print('Please provide a file name for plotting!')
                if type(filename) == list:
                    plot_model(self.resvae_model, to_file=filename[np.where(model == 'rlvae')[0]])
                else:
                    plot_model(self.resvae_model, to_file=filename)

    def add_latent_labels(self, classes):
        """
        Utility function to infer the latent variable dimension labels from the class labels and add it to the model. Labels can also be added manually trough modifying the .classes variable.
        
        :param classes: List of strings containing the class labels
        :return: None
        """
        latent_scale = self.config['LATENT_SCALE']
        self.classes = [x + '_' + str(y) for x in classes for y in range(latent_scale)]
        return None

    def load_model(self, model_file, model_weights):
        """
        Utility function to load models and their weights.

        :param model_file: File including path of the \*_resvae.\* model
        :param model_weights: File including path of the \*_resvae_weights.h5 weights
        :return: None
        """
        assert os.path.isfile(model_file), print('model file does not exist.')
        assert model_file.split('_')[-1].split('.')[0] == 'resvae', print('please use *_resvae.* model file')
        if model_file.split('.')[-1] == 'json':
            json_file = open(model_file, 'r')
            self.resvae_model = model_from_json(json_file.read())
            json_file.close()
            json_file = open(model_file.replace('_resvae.json', '_encoder.json'), 'r')
            self.encoder = model_from_json(json_file.read())
            json_file.close()
            json_file = open(model_file.replace('_resvae.json', '_decoder.json'), 'r')
            self.decoder = model_from_json(json_file.read())
            json_file.close()
            if model_weights is not None:
                assert os.path.isfile(model_weights), print('weights file does not exist')
                self.resvae_model.load_weights(model_weights)
                self.encoder.load_weights(model_weights.replace('_resvae_weights.h5', '_encoder_weights.h5'))
                self.decoder.load_weights(model_weights.replace('_resvae_weights.h5', '_decoder_weights.h5'))
        elif model_file.split('.')[-1] == 'h5':
            self.resvae_model = load_model(model_file)
            self.encoder = load_model(model_file.replace('_resvae.h5', '_encoder.json'))
            self.decoder = load_model(model_file.replace('_resvae.h5', '_decoder.json'))
        return None

    def get_latent_space(self, exprs: np.ndarray, classes: np.ndarray, cluster_index=None):
        """
        Utility function to return the activation of the latent space, given an input.

        :param exprs: Expression matrix (samples x genes)
        :param classes: One-hot encoded class matrix (samples x classes)
        :param cluster_index: The index of the cluster (according to the one-hot encoding) to be extracted. If None, returns all clusters
        :return: a numpy array of shape samples x neurons containing the neuron activations by each sample
        """
        if cluster_index is None:
            cluster_index = np.arange(self.config.INPUT_SHAPE[1])
        latent_space = self.encoder.predict([exprs, classes])[2]
        latent_space = np.reshape(latent_space, (len(exprs), self.config.INPUT_SHAPE[1], self.config.LATENT_SCALE))
        latent_space = latent_space[:, cluster_index, :]
        latent_space = latent_space.reshape((len(exprs), -1))
        if self.classes is not None:
            latent_space = pd.DataFrame(data=latent_space, columns=self.classes)
        else:
            latent_space = pd.DataFrame(data=latent_space)
        return latent_space

    def get_latent_to_gene(self, normalized: bool = False, direction: bool = True):
        """
        Extracts the weight mappings from the latent space (i.e. each cell type) to the output layer embedding the genes. Propagation of weights is realized as matrix multiplication of each intermediate layer's weight matrix.

        :param normalized: Whether to normalize the results by gene (default: False)
        :param direction: Return absolute (False) or directional (True) weights. (default: True)
        :return: Neuron-to-gene mappings for the hidden layer (pd.DataFrame)
        """
        num_weights = len(self.decoder.get_weights())
        result = self.decoder.get_weights()[0]
        for layer in range(1, num_weights, 1):
            if np.ndim(self.decoder.get_weights()[layer]) == 2:
                result = np.matmul(result, self.decoder.get_weights()[layer])
        if normalized:
            (result - result.mean(axis=0)) / result.std(axis=0)
        if self.genes is not None:
            if self.classes is not None:
                result = pd.DataFrame(data=result, columns=self.genes, index=self.classes)
            else:
                result = pd.DataFrame(data=result, columns=self.genes)
        elif self.classes is not None:
            result = pd.DataFrame(data=result, index=self.classes)
        else:
            result = pd.DataFrame(data=result)
        if direction:
            return result
        else:
            return np.abs(result)

    def get_neuron_to_gene(self, normalized: bool = False, initial_layer: int = 1, direction: bool = True):
        """
        Returns the weight mappings from intermediate decoder layer neurons to the output layer with gene embeddings. Weight propagation is realized by matrix multiplication of weight matrices.

        :param normalized: Whether to normalize the results by gene (default: False)
        :param initial_layer: Index of the decoder layer to output mappings for (default: 1)
        :param direction: Return absolute (False) or directional (True) weights. (default: True)
        :return: Neuron-to-gene mappings for a decoder layer (pd.DataFrame)
        """
        result = None
        weight_matrix_ind = np.argwhere(np.asarray([np.ndim(x) for x in self.decoder.get_weights()]) == 2).flatten()
        init = initial_layer
        num_weights = len(weight_matrix_ind)
        result = self.decoder.get_weights()[weight_matrix_ind[init]]
        for layer in range(init + 1, num_weights, 1):
            result = np.matmul(result, self.decoder.get_weights()[weight_matrix_ind[layer]])
        if normalized:
            result = (result - result.mean(axis=0)) / result.std(axis=0)
        if self.genes is not None:
            result = pd.DataFrame(data=result, columns=self.genes)
        else:
            result = pd.DataFrame(data=result)
        if direction:
            return result
        else:
            return np.abs(result)

    def get_latent_to_neuron(self, normalized: bool = False, target_layer: int = 1, direction: bool = True):
        target = target_layer
        num_weights = len(self.decoder.get_weights())
        result = self.decoder.get_weights()[0]
        if target_layer > 1:
            for layer in range(1, num_weights, 1):
                if np.ndim(self.decoder.get_weights()[layer]) == 2:
                    target -= 1
                    result = np.matmul(result, self.decoder.get_weights()[layer])
                if target == 1:
                    break
        if self.classes is not None:
            result = pd.DataFrame(data=result, index=self.classes)
        else:
            result = pd.DataFrame(data=result)
        if normalized:
            result = (result - result.mean(axis=0)) / result.std(axis=0)
        result = pd.DataFrame(data=result)
        # TODO: fix directionality issue
        if direction:
            return result
        else:
            return np.abs(result)

    def get_gene_biases(self, relative: bool = False):
        """
        Returns the biases of the last (output layer

        :param relative: Outputs absolute biases relative to the absolute sum of inbound weight mappings
        :return: a 1D numpy ndarray of biases, length (genes)
        """
        if relative:
            return np.abs(self.decoder.get_weights()[-1]) / np.abs(np.sum(self.get_latent_to_gene(), axis=0))
        else:
            return self.decoder.get_weights()[-1]

    def save_config(self, outfile: str = 'models/config.json'):
        """
        Saves the config variable as json file.

        :param outfile: Path to the desired output file
        :return: None
        """
        if not os.path.isdir(os.path.split(outfile)[0]):
            os.mkdir(os.path.split(outfile)[0])
        dictionary = self.config
        with open(outfile, 'w') as json_file:
            json.dump(dictionary, json_file)
        return None

    def load_config(self, infile: str = 'models/config.json'):
        """
        Loads a config file stored as json.

        :param infile: Path to the .json file
        :return: None
        """
        assert (os.path.isfile(infile)), print('File does not exist')
        with open(infile) as handle:
            dictionary = json.loads(handle.read())
        self.config = dictionary
        return None

    def save_model_new(self, model_dir: str, model_name: str = 'my_model'):
        """
        Utility function to save model weights and configurations.

        :param model_dir: Directory to save model in
        :param model_name: Base name of the model files (default: my_model)
        :return: None
        """
        if model_dir == None:
            model_dir = self.model_dir
        assert os.path.isdir(model_dir), print('model directory not found')
        assert self.isfit, print('Model has not been trained. To save the config, use save_config')
        self.resvae_model.save_weights(os.path.join(model_dir, str(model_name + '_resvae_weights.h5')))
        self.encoder.save_weights(os.path.join(model_dir, str(model_name + '_encoder_weights.h5')))
        self.decoder.save_weights(os.path.join(model_dir, str(model_name + '_decoder_weights.h5')))
        self.save_config(os.path.join(model_dir, str(model_name + '.config')))

    def load_model_new(self, model_dir: str, model_name: str = 'my_model'):
        """
        Utility function to load models and their weights.

        :param model_dir: Directory in which the model was saved
        :param model_name: base name of the model
        :return: None
        """
        assert os.path.isdir(model_dir), print('model directory does not exist.')
        assert os.path.isfile(os.path.join(model_dir, str(model_name + '_resvae_weights.h5'))), \
            print('model file not found')
        assert os.path.isfile(os.path.join(model_dir, str(model_name + '_encoder_weights.h5'))), \
            print('model file not found')
        assert os.path.isfile(os.path.join(model_dir, str(model_name + '_encoder_weights.h5'))), \
            print('model file not found')
        assert os.path.isfile(os.path.join(model_dir, str(model_name + '.config'))), \
            print('config file not found')
        self.load_config(os.path.join(model_dir, str(model_name + '.config')))
        self.built = False
        self.encoder, self.decoder, self.resvae_model = self.build()
        self.encoder.load_weights(os.path.join(model_dir, str(model_name + '_encoder_weights.h5')))
        self.decoder.load_weights(os.path.join(model_dir, str(model_name + '_decoder_weights.h5')))
        self.resvae_model.load_weights(os.path.join(model_dir, str(model_name + '_resvae_weights.h5')))
        self.compile()
        return None

    def calc_ch_score(self, exprs=None, normalized: bool = True, target='genes', source='latent',
                      permute=10, direction=True, index_source=1, index_target=1, use_negative=False):
        """
        Function to calculate the Calinski-Harabasz score (Variance Ratio Criterion) on the different layers.

        :param exprs: Expression matrix. Numpy array of shape samples x features
        :param normalized: Whether to normalize results by feature (default: True)
        :param target: Whether the target is 'genes' or a decoder layer 'neurons' (default: 'genes')
        :param source: The source layer, 'latent' or 'neurons' (default: 'latent')
        :param permute: How many random permutations to perform (default: 10)
        :param direction: Whether to use directionality of weights instead of absolute values (default: True)
        :param index_source: Which source layer to use with neuron to gene mappings (default: 1)
        :param index_target: Which target layer to use with latent to neuron mappings (default: 1)
        :param use_negative: Whether to use negative weights in the calculation (default: False)
        :return: two 1D numpy array with the scores, one with real scores, the second for permutations
        """
        weights = None
        if source == 'latent':
            if target == 'genes':
                weights = self.get_latent_to_gene(normalized=normalized,
                                                  direction=direction)
            else:
                weights = self.get_latent_to_neuron(normalized=normalized,
                                                    target_layer=index_target,
                                                    direction=direction)
        if source == 'neurons':
            if target == 'genes':
                weights = self.get_neuron_to_gene(normalized=normalized,
                                                  direction=direction,
                                                  initial_layer=index_source)
            else:
                print('Sorry, neuron to neuron mapping is not implemented yet')
        ch_real = []
        ch_permute = []
        for i in range(weights.shape[0]):
            cluster = i
            genes_c = np.asarray(self.genes).copy()
            pos_cutoff = cutils.calculate_elbow(weights.iloc[cluster, :])
            genes_c[weights.iloc[cluster, :] >= np.sort(weights.iloc[cluster, :])[pos_cutoff]] = 'top'
            genes_c[weights.iloc[cluster, :] < np.sort(weights.iloc[cluster, :])[pos_cutoff]] = 'bottom'
            ch_real.append(calinski_harabasz_score(exprs.T, genes_c))
            for i in range(permute):
                genes_permute = np.random.permutation(genes_c)
                ch_permute.append(calinski_harabasz_score(exprs.T, genes_permute))
            if direction == True and use_negative == True:
                neg_cutoff = cutils.calculate_elbow(weights.iloc[cluster, :], negative=True)
                genes_c[weights.iloc[cluster, :] <= np.sort(weights.iloc[cluster, :])[neg_cutoff]] = 'top'
                genes_c[weights.iloc[cluster, :] > np.sort(weights.iloc[cluster, :])[neg_cutoff]] = 'bottom'
                ch_real.append(calinski_harabasz_score(exprs.T, genes_c))
                for i in range(permute):
                    genes_permute = np.random.permutation(genes_c)
                    ch_permute.append(calinski_harabasz_score(exprs.T, genes_permute))
        ch_real = np.asarray(ch_real)
        ch_permute = np.asarray(ch_permute)
        return ch_real, ch_permute

    def calc_fpc(self, normalized: bool = True, target='genes', source='latent',
                 direction=True, index_source=1, index_target=1, use_negative=False):
        """
        Function to calculate the fuzzy partition coefficient on the different weight matrices.

        :param normalized: Whether to normalize results by feature (default: True)
        :param target: Whether the target is 'genes' or a decoder layer 'neurons' (default: 'genes')
        :param source: The source layer, 'latent' or 'neurons' (default: 'latent')
        :param direction: Whether to use directionality of weights instead of absolute values (default: True)
        :param index_source: Which source layer to use with neuron to gene mappings (default: 1)
        :param index_target: Which target layer to use with latent to neuron mappings (default: 1)
        :param use_negative: Whether to use negative weights in the calculation (default: False)
        :return: the FPC for the actual weight matrix
        """
        weights = None
        if source == 'latent':
            if target == 'genes':
                weights = self.get_latent_to_gene(normalized=normalized,
                                                  direction=direction)
            else:
                weights = self.get_latent_to_neuron(normalized=normalized,
                                                    target_layer=index_target,
                                                    direction=direction)
        if source == 'neurons':
            if target == 'genes':
                weights = self.get_neuron_to_gene(normalized=normalized,
                                                  direction=direction,
                                                  initial_layer=index_source)
            else:
                print('Sorry, neuron to neuron mapping is not implemented yet')
        if direction == True and use_negative == False:
            weights[weights < 0] = 0
        fpc = cutils.calculate_fpc(weights)
        return fpc

    def mappings_to_file(self, filename: str = 'mappings.hdf5', normalized: bool = True):
        """
        This saves the weight mappings to a hdf5 file that can later be imported into the frontend.

        :param filename: The name of the weight mappings file.
        :param normalized: Whether to save normalized weights. default: True
        :return: None
        """
        weights_clusters = self.get_latent_to_gene(normalized=normalized)
        weights_neurons1 = self.get_neuron_to_gene(normalized=normalized, initial_layer=1)
        weights_neurons2 = self.get_neuron_to_gene(normalized=normalized, initial_layer=2)
        weights_latent_neurons1 = self.get_latent_to_neuron(normalized=normalized, target_layer=1)
        weights_latent_neurons2 = self.get_latent_to_neuron(normalized=normalized, target_layer=2)
        weights_clusters.to_hdf(filename, 'weights/latent_genes', table=True, mode='a')
        weights_neurons1.to_hdf(filename, 'weights/neuron1_genes', table=True, mode='a')
        weights_neurons2.to_hdf(filename, 'weights/neuron2_genes', table=True, mode='a')
        weights_latent_neurons1.to_hdf(filename, 'weights/latent_neurons1', table=True, mode='a')
        weights_latent_neurons2.to_hdf(filename, 'weights/latent_neurons2', table=True, mode='a')
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', '-c', help='Path to the configuration file', type=str)
    parser.add_argument('--exprs', '-x', help='Path to the expression matrix', type=str)
    parser.add_argument('--classes', '-y', help='Path to the class file', type=str)
    parser.add_argument('--model_dir', '-d', help='Path to model output directory', type=str)
    parser.add_argument('--model_name', '-n', help='Model base name', type=str)
    parser.add_argument('--write_weights', '-s', help='True or False; whether to write the weight mappings', type=bool)
    args = parser.parse_args()
    assert os.path.isfile(args.config), print('configuration file does not exist')
    assert os.path.isfile(args.exprs), print('expression matrix not found')
    assert os.path.isfile(args.classes), print('class file not found')
    assert os.path.isdir(args.model_dir), print('model dir does not exist')
    print('Loading expression matrix...')
    try:
        exprs, genes = cutils.load_exprs(args.exprs)
    except:
        print('Unexpected error when loading expression matrix:', sys.exc_info()[0])
        raise
    print('Normalizing expression matrix...')
    try:
        exprs_norm = cutils.normalize_count_matrix(exprs)
    except:
        print('Unexpected error when normalizing expression matrix:', sys.exc_info()[0])
        raise
    print('Loading and encoding class vector...')
    try:
        classes = np.loadtxt(args.classes)
        classes, _ = cutils.one_hot_encoder(classes)
    except:
        print('Unexpected error when loading or encoding classes:', sys.exc_info()[0])
        raise
    print('Initializing model...')
    try:
        my_resvae = MeiNN(args.model_dir, args.config)
        my_resvae.compile()
        my_resvae.genes = genes
    except:
        print('Unexpected error when initializing model:', sys.exc_info()[0])
        raise
    print('Fitting model...')
    try:
        my_resvae.fit(exprs=exprs_norm, classes=classes, model_dir=args.model_dir, model_name=args.model_name)
    except:
        print('Unexpected error when fitting model:', sys.exc_info()[0])
        raise
    print('Saving model')
    try:
        my_resvae.save_model_new()
    except:
        print('Unexpected error when saving model:', sys.exc_info()[0])
        raise
    print('Extracting weights')
    try:
        weights_classes = my_resvae.get_latent_to_gene()
        weights_neurons_1 = my_resvae.get_neuron_to_gene(initial_layer=0)
        weights_classes_neurons_1 = my_resvae.get_latent_to_neuron(target_layer=0)
        if len(my_resvae.config['DECODER_SHAPE']) > 1:
            weights_neurons_2 = my_resvae.get_neuron_to_gene(initial_layer=1)
            weights_classes_neurons_2 = my_resvae.get_latent_to_neuron(target_layer=1)
    except:
        print('Unexpected error when obtaining weights:', sys.exc_info()[0])
        raise
    print('Saving weights...')
    try:
        weights_classes.to_csv(os.path.join(args.model_dir, str(args.model_name + '_weights_classes.csv')))
        weights_neurons_1.to_csv(os.path.join(args.model_dir, str(args.model_name + '_weights_neurons_1.csv')))
        weights_classes_neurons_1.to_csv(os.path.join(args.model_dir,
                                                      str(args.model_name + '_weights_classes_neurons_1.csv')))
        if len(my_resvae.config['DECODER_SHAPE']) > 1:
            weights_neurons_2.to_csv(os.path.join(args.model_dir, str(args.model_name + '_weights_neurons_2.csv')))
            weights_classes_neurons_2.to_csv(os.path.join(args.model_dir,
                                                          str(args.model_name + '_weights_classes_neurons_2.csv')))
    except:
        print('Unexpected error when saving weights:', sys.exc_info()[0])
        raise
    print('Done! resVAE did not encounter any errors.')

    return 1


if __name__ == '__main__':
    main()
