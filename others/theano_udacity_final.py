###############################################################
#                        THE FINAL UDACITY PROJECT
#                           WORD REVERSER
###############################################################
import os
os.environ["THEANO_FLAGS"] = "mode=FAST_RUN,device=cpu,floatX=float32"

# THEANO
import numpy as np
import theano
import theano.tensor as T
from theano.tensor.shared_randomstreams import RandomStreams as RandomStreams

# I/O
import pickle
import timeit
import sys
import zipfile
import string
from six.moves.urllib.request import urlretrieve
import copy
import re

# MATH
import random
from math import e,log,sqrt,isnan

# LAYERS
from vudu.layer import OneHot,EmbedLayer,LSTMLayer,LinearLayer,SoftmaxLayer

# HELPERS
from vudu.wordHelpers import WordHelper
from vudu import utils

# INIT RANDOM
srng = RandomStreams()
####################################################################################################
# CONSTANTS

# VARIABLES INIT
X_LIST = T.vector('x_list')
X = T.scalar('x')

Y_LIST = T.matrix('y_list')
Y = T.vector('y')

S1 = T.matrix('hidden_state1')
H1 = T.matrix('hidden_update1')

S2 = T.matrix('hidden_state2')
H2 = T.matrix('hidden_update2')

S3 = T.matrix('hidden_state3')
H3 = T.matrix('hidden_update3')

NUM_PRED = T.iscalar('number_of_preds')
INIT_PRED = T.scalar('init_pred')

# Intiate Word Helpers
vocab = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z']
try:
    with open('word_helpers_udacity.pkl','rb') as f:
        wh = pickle.load(f) # use encoding='latin1' if converting from python2 object to python3 instance
    print('loaded previous wordHelper object')
except:
    wh = WordHelper(vocab,max_word_size=6)
    with open('word_helpers_udacity.pkl','wb+') as f:
            pickle.dump(wh,f)
    print("created new wordHelper object")
    

# BATCHES
batch_size = 1 # MAX_WORD_SIZE
embed_size = 10
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
        updates.append((p, p - ((lr * g) / T.sqrt(new_m + 1e-6))))
    return updates

class RNN:
    def __init__(self,vocab_size,embed_size,hidden_layer_sizes,batch_size,dropout=None):
        self.batch_size = batch_size
        self.vocab_size = vocab_size
        # Input Layer
        self.input_layer = OneHot(vocab_size,batch_size,wh.eos)#EmbedLayer(vocab_size,embed_size,batch_size)
        # Init update parameters
        self.update_params = self.input_layer.update_params
        # Init memory parameters fo Adagrad
        self.memory_params = self.input_layer.memory_params
        
        # Hidden layer
        layer_sizes = [self.input_layer.y] + hidden_layer_sizes
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
    # entire network.
    # The pred_unused is the input from the sequence we use to kick
    # off the prediction.  We don't actually need a value, just a
    # sequence of same length as our input word so we know how many
    # letters to predict.
    def calc_preds(self,INIT_PRED,S1,H1,S2,H2,S3,H3):
        e = self.input_layer.forward_prop(INIT_PRED)
        S1,H1 = self.hidden_layer_1.forward_prop(e,S1,H1)
        S2,H2 = self.hidden_layer_2.forward_prop(H1,S2,H2)
        S3,H3 = self.hidden_layer_3.forward_prop(H2,S3,H3)
        pred = self.output_layer.forward_prop(H3)
        INIT_PRED = T.cast(T.argmax(pred),theano.config.floatX)  # argmax returns an int, we need to keep everything floatX
        return pred,INIT_PRED,S1,H1,S2,H2,S3,H3

    def calc_cost(self,pred,Y):
        return T.mean(T.nnet.categorical_crossentropy(pred,Y))
        
    
#nodes = [512,512,512]
nodes = [128,256,128]
#nodes = [100,100,100]

try:
    rnn = utils.load_net('udacity') 
except:
    rnn = RNN(wh.vocab_size,embed_size,nodes,batch_size)
    print("created new network")

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
                              sequences=None,
                              n_steps=NUM_PRED
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
forward_prop = theano.function(inputs=[X_LIST,S1,H1,S2,H2,S3,H3], outputs=[f_hidden_state1,f_hidden_output1,f_hidden_state2,f_hidden_output2,f_hidden_state3,f_hidden_output3], updates=None, allow_input_downcast=True)
back_prop = theano.function(inputs=[NUM_PRED,INIT_PRED,S1,H1,S2,H2,S3,H3,Y_LIST], outputs=[scan_cost,hidden_state1,hidden_output1,hidden_state2,hidden_output2,hidden_state3,hidden_output3], updates=updates, allow_input_downcast=True)

y_pred = y_preds[-1]
predict = theano.function(inputs=[NUM_PRED,INIT_PRED,S1,H1,S2,H2,S3,H3], outputs=[y_preds,hidden_state1,hidden_output1,hidden_state2,hidden_output2,hidden_state3,hidden_output3], updates=None, allow_input_downcast=True)


print("Model initialized, beginning training")

def predWord(word):
    # RESET HIDDENS
    hidden_state1 = np.zeros(rnn.hidden_layer_1.hidden_state_shape)
    hidden_output1 = np.zeros(rnn.hidden_layer_1.hidden_output_shape)
    hidden_state2 = np.zeros(rnn.hidden_layer_2.hidden_state_shape)
    hidden_output2 = np.zeros(rnn.hidden_layer_2.hidden_output_shape)
    hidden_state3 = np.zeros(rnn.hidden_layer_3.hidden_state_shape)
    hidden_output3 = np.zeros(rnn.hidden_layer_3.hidden_output_shape)
    # Prepare forward prop
    init_pred = wh.char2id(wh.eos)
    pred_input = []
    for i in range(len(word)):
        pred_input.append(wh.char2id(word[i]))
    hidden_state1,hidden_output1,hidden_state2,hidden_output2,hidden_state3,hidden_output3 = forward_prop(pred_input,hidden_state1,hidden_output1,hidden_state2,hidden_output2,hidden_state3,hidden_output3)
    # Get Preds
    predictions,hidden_state1,hidden_output1,hidden_state2,hidden_output2,hidden_state3,hidden_output3 = predict(len(word),init_pred,hidden_state1,hidden_output1,hidden_state2,hidden_output2,hidden_state3,hidden_output3)
    pred_word = ''.join([wh.id2char(np.random.choice(wh.vocab_indices, p=p.ravel())) for p in predictions])
    return pred_word

def predictTest():
    test_corpus = ['the','quick','brown','fox','jumps']
    output = ''
    init_pred = 0
    for _ in range(len(test_corpus)):
        # Prepare prediction inputs
        word = test_corpus[_]
        pred = predWord(word)
        output += pred + ' '
    print("prediction:",output,'true:',' '.join(test_corpus))

if hasattr(rnn,'current_loss'):
    smooth_loss = rnn.current_loss
else:
    smooth_loss = -np.log(1.0/wh.vocab_size)*seq_length
    
n = 0
p = 0
init_pred = 0
try:
    while True:
        # Reset memory
        hidden_state1 = np.zeros(rnn.hidden_layer_1.hidden_state_shape)
        hidden_output1 = np.zeros(rnn.hidden_layer_1.hidden_output_shape)
        hidden_state2 = np.zeros(rnn.hidden_layer_2.hidden_state_shape)
        hidden_output2 = np.zeros(rnn.hidden_layer_2.hidden_output_shape)
        hidden_state3 = np.zeros(rnn.hidden_layer_3.hidden_state_shape)
        hidden_output3 = np.zeros(rnn.hidden_layer_3.hidden_output_shape)
        init_pred = wh.char2id(wh.eos)
        c_input = wh.genRandWord()
        c_output = c_input[::-1]#wh.reverseWord(c_input)

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
        loss,hidden_state1,hidden_output1,hidden_state2,hidden_output2,hidden_state3,hidden_output3 = back_prop(len(batch_input),init_pred,hidden_state1,hidden_output1,hidden_state2,hidden_output2,hidden_state3,hidden_output3,batch_output)
        smooth_loss = smooth_loss * 0.999 + loss * 0.001
            
        if not n % 100:
            predictTest()
            print("Completed iteration:",n,"Cost: ",smooth_loss)

        if not n % 10000:
            rnn.current_loss = smooth_loss
            utils.save_net(rnn,'udacity',n)
        n += 1
        
except KeyboardInterrupt:
    utils.save_net(rnn,'udacity',n)
        
print("Training complete")

      

