###############################################################
#                        THE FINAL UDACITY PROJECT
#                           WORD REVERSER
###############################################################

# THEANO
import numpy as np
import theano
import theano.tensor as T
from theano.sandbox.rng_mrg import MRG_RandomStreams as RandomStreams

# I/O
import pickle
import os
import timeit
import sys
import zipfile
import string
from six.moves.urllib.request import urlretrieve
import copy
import re

# MATH
import random
from math import e,log,sqrt

# LAYERS
from layer import OneHot,EmbedLayer,LSTMLayer,LinearLayer,SoftmaxLayer

# HELPERS
from wordHelpers import WordHelper
import utils

# INIT RANDOM
srng = RandomStreams()
####################################################################################################
# CONSTANTS

# VARIABLES INIT
X_LIST = T.ivector('x_list')
X = T.iscalar('x')

Y_LIST = T.imatrix('y_list')
Y = T.ivector('y')

S1 = T.dmatrix('hidden_state1')
H1 = T.dmatrix('hidden_update1')

S2 = T.dmatrix('hidden_state2')
H2 = T.dmatrix('hidden_update2')

S3 = T.dmatrix('hidden_state3')
H3 = T.dmatrix('hidden_update3')

PRED_LIST = T.ivector('pred_list')
INIT_PRED = T.iscalar('init_pred')

# LOAD DATA
# New toy problem:
# first couple paragraphs from a random Federalist paper
with open('input.txt','r') as f:
    data = f.read()
f.close()
corpus = re.split('\W+',data.lower())
corpus_len = len(corpus)
print("data loaded: {}".format(corpus_len))

# Initialize wordhelper functions
vocab = list(set(''.join(corpus)))
wh = WordHelper(vocab)

# BATCHES
batch_size = 1 # MAX_WORD_SIZE
embed_size = 100
seq_length = 8 # average word length
#num_batches = int(corpus_len/seq_length)

# TRAINING PARAMS
n_epochs = 100000
cur_epoch = 0
cur_grad = 0.
use_saved = False
    
####################################################################################################
# MODEL AND OPTIMIZATION
####################################################################################################

# RMSprop is for NERDS
def Adagrad(cost, params, mem, lr=0.1):
    grads = T.grad(cost=cost, wrt=params)
    updates = []
    for p,g,m in zip(params, grads, mem):
        g = T.clip(g,-5.,5)
        new_m = m + (g * g)
        updates.append((m,new_m))
        updates.append((p, p - ((lr * g) / T.sqrt(new_m + 1e-8))))
    return updates

class RNN:
    def __init__(self,vocab_size,embed_size,hidden_layer_sizes,batch_size,dropout=None):
        self.batch_size = batch_size
        self.vocab_size = vocab_size
        # Input Layer
        self.input_layer = EmbedLayer(vocab_size,embed_size,batch_size)
        # Init update parameters
        self.update_params = self.input_layer.update_params
        # Init memory parameters fo Adagrad
        self.memory_params = self.input_layer.memory_params
        
        # Hidden layer
        layer_sizes = [embed_size] + hidden_layer_sizes
        self.hidden_layer_names = []
        for i in range(len(layer_sizes)-1):
            name = 'hidden_layer_{}'.format(i+1) # begin names at 1, not 0
            self.hidden_layer_names.append(name)
            hl = LSTMLayer(layer_sizes[i],
                               layer_sizes[i+1],
                               batch_size,
                               name)
            setattr(self,name,hl)                
            # Add the update parameters to the rnn class
            self.update_params += hl.update_params
            self.memory_params += hl.memory_params

        # Output Layer
        self.output_layer = SoftmaxLayer(hidden_layer_sizes[-1],vocab_size)
        # Update Parameters - Backprop
        self.update_params += self.output_layer.update_params
        # Memory Parameters for Adagrad
        self.memory_params += self.output_layer.memory_params

    # pass the word into the network to set all the hidden states.
    def set_hiddens(self,X,S1,H1,S2,H2,S3,H3):
        e = self.input_layer.forward_prop(X)
        S1,H1 = self.hidden_layer_1.forward_prop(e,S1,H1)
        S2,H2 = self.hidden_layer_2.forward_prop(H1,S2,H2)
        S3,H3 = self.hidden_layer_3.forward_prop(H2,S3,H3)
        return S1,H1,S2,H2,S3,H3

    # make predictions after the word has been sent through the
    # entire network
    def calc_preds(self,INIT_PRED,S1,H1,S2,H2,S3,H3):
        e = self.input_layer.forward_prop(INIT_PRED)
        S1,H1 = self.hidden_layer_1.forward_prop(e,S1,H1)
        S2,H2 = self.hidden_layer_2.forward_prop(H1,S2,H2)
        S3,H3 = self.hidden_layer_3.forward_prop(H2,S3,H3)
        pred = self.output_layer.forward_prop(H3)
        INIT_PRED = wh.onehot2id(pred)
        return pred,INIT_PRED,S1,H1,S2,H2,S3,H3

    def calc_cost(self,pred,Y):
        return T.mean(T.nnet.categorical_crossentropy(pred,Y))
        
    
nodes = [256,256,256]

rnn = RNN(wh.vocab_size,embed_size,nodes,batch_size)
params = rnn.update_params
memory_params = rnn.memory_params

outputs_info=[dict(initial=S1, taps=[-1]),dict(initial=H1, taps=[-1]),
              dict(initial=S2, taps=[-1]),dict(initial=H2, taps=[-1]),
              dict(initial=S3, taps=[-1]),dict(initial=H3, taps=[-1])
              ]
# The f_ stands for forward_prop
f_states1,f_outputs1,f_states2,f_outputs2,f_states3,f_outputs3 = theano.scan(fn=rnn.set_hiddens,
                              outputs_info=outputs_info,
                              sequences=[X_LIST]
                            )[0] # only need the results, not the updates

f_hidden_state1 = f_states1[-1]
f_hidden_output1 = f_outputs1[-1]
f_hidden_state2 = f_states2[-1]
f_hidden_output2 = f_outputs2[-1]
f_hidden_state3 = f_states3[-1]
f_hidden_output3 = f_outputs3[-1]

preds_info=[None,dict(initial=INIT_PRED, taps=[-1]),dict(initial=S1, taps=[-1]),dict(initial=H1, taps=[-1]),
                                               dict(initial=S2, taps=[-1]),dict(initial=H2, taps=[-1]),
                                               dict(initial=S3, taps=[-1]),dict(initial=H3, taps=[-1])
              ]

y_preds, id_preds, states1,outputs1,states2,outputs2,states3,outputs3 = theano.scan(fn=rnn.calc_preds,
                              outputs_info=preds_info,
                              sequences=[PRED_LIST]
                            )[0] # only need the results, not the updates

scan_costs = theano.scan(fn=rnn.calc_cost,
                              outputs_info=None,
                              sequences=[y_preds,Y_LIST]
                            )[0] # only need the results, not the updates

scan_cost = T.sum(scan_costs)
hidden_state1 = states1[-1]
hidden_output1 = outputs1[-1]
hidden_state2 = states2[-1]
hidden_output2 = outputs2[-1]
hidden_state3 = states3[-1]
hidden_output3 = outputs3[-1]
updates = Adagrad(scan_cost,params,memory_params)
forward_prop = theano.function(inputs=[X_LIST,S1,H1,S2,H2,S3,H3], outputs=[f_states1,f_outputs1,f_states2,f_outputs2,f_states3,f_outputs3], updates=None)
back_prop = theano.function(inputs=[PRED_LIST,Y_LIST,S1,H1,S2,H2,S3,H3], outputs=[scan_cost,hidden_state1,hidden_output1,hidden_state2,hidden_output2,hidden_state3,hidden_output3], updates=updates)

#grads = T.grad(cost=scan_cost, wrt=params)
#test_grads  = theano.function(inputs=[X_LIST,Y_LIST,H], outputs=grads, updates=None, allow_input_downcast=True)

y_pred = y_preds[-1]
predict = theano.function(inputs=[X_LIST,Y_LIST,S1,H1,S2,H2,S3,H3], outputs=[y_preds,hidden_state1,hidden_output1,hidden_state2,hidden_output2,hidden_state3,hidden_output3], updates=None, allow_input_downcast=True)

#test_hidden = theano.function(inputs=[X_LIST,Y_LIST,S1,H1,S2,H2,S3,H3], outputs=[states,outputs], updates=None, allow_input_downcast=True)

print("Model initialized, beginning training")

def predictTest():
    test_corpus = corpus[:5]#['the','quick','brown','fox','jumped']
    output = []
    hidden_state1 = np.zeros(rnn.hidden_layer_1.hidden_state_shape)
    hidden_output1 = np.zeros(rnn.hidden_layer_1.hidden_output_shape)
    hidden_state2 = np.zeros(rnn.hidden_layer_2.hidden_state_shape)
    hidden_output2 = np.zeros(rnn.hidden_layer_2.hidden_output_shape)
    hidden_state3 = np.zeros(rnn.hidden_layer_3.hidden_state_shape)
    hidden_output3 = np.zeros(rnn.hidden_layer_3.hidden_output_shape)
    for _ in range(5):
        word = test_corpus[_]
        pred_input = []
        pred_output_UNUSED = []
        for i in range(len(word)):
            pred_input.append(wh.char2id(word[i]))
            # This value is only used to trigger the calc_cost.
            # It's incorrect, but it doesn't update the parameters to that's okay.
            # Not great, but okay.
            pred_output_UNUSED.append(wh.id2onehot(wh.char2id(word[i])))
        hidden_state1,hidden_output1,hidden_state2,hidden_output2,hidden_state3,hidden_output3 = forward_prop(pred_input,hidden_state1,hidden_output1,hidden_state2,hidden_output2,hidden_state3,hidden_output3)
        predictions,hidden_state1,hidden_output1,hidden_state2,hidden_output2,hidden_state3,hidden_output3 = predict(pred_input,pred_output_UNUSED,hidden_state1,hidden_output1,hidden_state2,hidden_output2,hidden_state3,hidden_output3)
        for p in predictions:
            letter = wh.id2char(np.random.choice(range(wh.vocab_size), p=p.ravel()))
            output.append(letter)
        output.append(' ')
    print("prediction:",''.join(output),'true:',' '.join(test_corpus))

smooth_loss = -np.log(1.0/wh.vocab_size)*seq_length
n = 0
p = 0
while True:
    if p+seq_length+1 >= corpus_len or n == 0:
        # Reset memory
        hidden_state1 = np.zeros(rnn.hidden_layer_1.hidden_state_shape)
        hidden_output1 = np.zeros(rnn.hidden_layer_1.hidden_output_shape)
        hidden_state2 = np.zeros(rnn.hidden_layer_2.hidden_state_shape)
        hidden_output2 = np.zeros(rnn.hidden_layer_2.hidden_output_shape)
        hidden_state3 = np.zeros(rnn.hidden_layer_3.hidden_state_shape)
        hidden_output3 = np.zeros(rnn.hidden_layer_3.hidden_output_shape)
        p = 0 # go to beginning
    c_input = corpus[p]
    c_output = wh.reverseWord(corpus[p])

    batch_input = []
    batch_output = []
    for j in range(len(c_input)):
        c = c_input[j]
        c2 = c_output[j]
        batch_input.append(wh.char2id(c))
        batch_output.append(wh.id2onehot(wh.char2id(c2)))
    hidden_state1,hidden_output1,hidden_state2,hidden_output2,hidden_state3,hidden_output3 = forward_prop(batch_input,hidden_state1,hidden_output1,hidden_state2,hidden_output2,hidden_state3,hidden_output3)
    # Note that batch_input is passed here only to provide back_prop with the appropriate number of items to iterate over.
    # it could just as easily be an empty array of the same length
    loss,hidden_state1,hidden_output1,hidden_state2,hidden_output2,hidden_state3,hidden_output3 = back_prop(batch_input,batch_output,hidden_state1,hidden_output1,hidden_state2,hidden_output2,hidden_state3,hidden_output3)
    smooth_loss = smooth_loss * 0.999 + loss * 0.001

    if not n % 100:
        predictTest()
        print("Completed iteration:",n,"Cost: ",smooth_loss)

    p += seq_length
    n += 1

        
print("Training complete")
predictTest()
      
