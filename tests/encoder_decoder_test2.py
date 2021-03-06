import numpy as np
import theano
import theano.tensor as T

H = T.scalar('h')
G = T.scalar('g')
X = T.scalar('x')
X_LIST = T.vector('x_list')
# Proof of concept -- Shows that the inner dimension mismatch only occurs for non-matrices
Y = T.matrix('y')
Y_LIST = T.matrix('y_list')
NUM = T.iscalar('num')

# define a named function, rather than using lambda
def encode(X,H):
    H = H + 1.
    x = X + 2.
    return x,H

# NOTE
# NON-SEQUENCES GO 2nd
def decode(Y,G): 
    G = G / 2.
    y = Y - G
    return y,G

encode_info=[None,dict(initial=H, taps=[-1])]
encode_result, encode_updates = theano.scan(fn=encode,
                                        outputs_info=encode_info,
                                        sequences=[X_LIST]
                                        )
xs = encode_result[0]
Hs = encode_result[1]
encode_test = theano.function(inputs=[X_LIST,H], outputs=[xs,Hs], on_unused_input='warn')

# The initial state has to be dimension 1 greater than the value itself
decode_info=[dict(initial=Y_LIST, taps=[-1]),dict(initial=Hs, taps=[-1])]
decode_result, decode_updates = theano.scan(fn=decode,
                                        outputs_info=decode_info,
                                        n_steps=NUM#,
                                        #non_sequences=[Y]
                                        )

ys = decode_result[0]
Gs = decode_result[1]
cost = T.sum(ys)
decode_test = theano.function(inputs=[X_LIST,H,NUM,Y_LIST], outputs=[ys,Gs], on_unused_input='warn')

g = T.grad(cost=cost, wrt=[Hs])


# test
xs_test,Hs_test = encode_test([1],1)
print('xs: {}'.format(xs_test))
print('Hs: {}'.format(Hs_test))
ys_test,Gs_test = decode_test([1],1,3,[[1]])
print('ys: {}'.format(ys_test))
print('Gs: {}'.format(Gs_test))
