import numpy as np
import theano as theano
import theano.tensor as T
from utils import *

#Paper: REASONING ABOUT ENTAILMENT WITH NEURAL ATTENTION
class LSTM2:
    
    def __init__(self, classDim=0, wordDim=0, hiddenDim=0, senLen=0, batchSize=0, truncate=-1):
        # Assign instance variables
        # print classDim,wordDim,hiddenDim
        self.classDim  = classDim
        self.wordDim   = wordDim
        self.hiddenDim = hiddenDim
        self.senLen    = senLen
        self.batchSize = batchSize
        self.truncate = truncate
        C = np.random.uniform(0., 0., (classDim, classDim))
        for i in range(classDim): C[i][i]=1.0
        # Initialize the network parameters, Paper 2, 3
        E = np.random.uniform(-np.sqrt(1./wordDim), np.sqrt(1./wordDim), (wordDim, hiddenDim))          #Ebdding Matirx
        W = np.random.uniform(-np.sqrt(1./hiddenDim), np.sqrt(1./hiddenDim), (8, hiddenDim, hiddenDim * 4)) #W[0-1].dot(x), W[2-3].(i,f,o,c)
        B = np.random.uniform(-np.sqrt(1./hiddenDim), np.sqrt(1./hiddenDim), (4, hiddenDim * 4))             #B[0-1] for W[0-1]
        V = np.random.uniform(-np.sqrt(1./hiddenDim), np.sqrt(1./hiddenDim), (2, hiddenDim, classDim))         #LR W and b
        b = np.random.uniform(-np.sqrt(1./classDim), np.sqrt(1./classDim), (classDim))
        # Theano: Created shared variables
        self.C = theano.shared(value=C.astype(theano.config.floatX), name='C')
        self.E = theano.shared(value=E.astype(theano.config.floatX), name='E')
        self.W = theano.shared(value=W.astype(theano.config.floatX), name='W')
        self.B = theano.shared(value=B.astype(theano.config.floatX), name='B')
        self.V = theano.shared(value=V.astype(theano.config.floatX), name='V')
        self.b = theano.shared(value=b.astype(theano.config.floatX), name='b')
        # SGD / rmsprop: Initialize parameters
        self.mE = theano.shared(value=np.zeros(E.shape).astype(theano.config.floatX), name='mE')
        self.mW = theano.shared(value=np.zeros(W.shape).astype(theano.config.floatX), name='mW')
        self.mB = theano.shared(value=np.zeros(B.shape).astype(theano.config.floatX), name='mB')
        self.mV = theano.shared(value=np.zeros(V.shape).astype(theano.config.floatX), name='mV')
        self.mb = theano.shared(value=np.zeros(b.shape).astype(theano.config.floatX), name='mb')
        # We store the Theano graph here
        self.theano = {}
        self.__theano_build__()

    def __theano_build__(self):
        E, W, V, b, B, hiddenDim = self.E, self.W, self.V, self.b, self.B, self.hiddenDim

        x1  = T.imatrix('x1')    #first sentence
        x2  = T.imatrix('x2')    #second sentence
        x1_mask = T.fmatrix('x1_mask')    #mask
        x2_mask = T.fmatrix('x2_mask')
        y   = T.ivector('y')     #label
    
        #Embdding words
        _E1 = E.dot(W[0]) + B[0]
        _E2 = E.dot(W[1]) + B[1]
        statex1 = _E1[x1.flatten(), :].reshape([x1.shape[0], x1.shape[1], hiddenDim * 4])
        statex2 = _E2[x2.flatten(), :].reshape([x2.shape[0], x2.shape[1], hiddenDim * 4])
        
        def LSTM2Layer(x, mx, ph1, pc1, ph2, pc2, Wh1, Wx2, Wh2, B2):
            #first layer
            _x = ph1.dot(Wh1) + x
            i1  = T.nnet.hard_sigmoid(_x[:, hiddenDim * 0 : hiddenDim * 1])
            f1  = T.nnet.hard_sigmoid(_x[:, hiddenDim * 1 : hiddenDim * 2])
            o1  = T.nnet.hard_sigmoid(_x[:, hiddenDim * 2 : hiddenDim * 3])
            c1  = T.tanh(_x[:, hiddenDim * 3 : hiddenDim * 4])

            c1  = f1 * pc1 + i1 * c1
            c1  = mx[:, None] * c1 + (1.- mx[:,None]) * pc1
            
            h1  = o1 * T.tanh(c1)
            h1  = mx[:, None] * h1 + (1.- mx[:,None]) * ph1
            
            #second layer
            _x = h1.dot(Wx2) + ph2.dot(Wh2) + B2
            i2  = T.nnet.hard_sigmoid(_x[:, hiddenDim * 0 : hiddenDim * 1])
            f2  = T.nnet.hard_sigmoid(_x[:, hiddenDim * 1 : hiddenDim * 2])
            o2  = T.nnet.hard_sigmoid(_x[:, hiddenDim * 2 : hiddenDim * 3])
            c2  = T.tanh(_x[:, hiddenDim * 3 : hiddenDim * 4])

            c2  = f2 * pc2 + i2 * c2
            c2  = mx[:, None] * c2 + (1.- mx[:,None]) * pc2

            h2  = o2 * T.tanh(c2)
            h2  = mx[:, None] * h2 + (1.- mx[:,None]) * ph2

            return [h1, c1, h2, c2]  # size = sample * hidden : 3 * 4
            
        [h11, c11, h12, c12], updates = theano.scan(
            fn=LSTM2Layer,
            sequences=[statex1, x1_mask],
            truncate_gradient=self.truncate,
            outputs_info=[dict(initial=T.zeros([self.batchSize, self.hiddenDim])),
                          dict(initial=T.zeros([self.batchSize, self.hiddenDim])),
                          dict(initial=T.zeros([self.batchSize, self.hiddenDim])),
                          dict(initial=T.zeros([self.batchSize, self.hiddenDim]))],
            non_sequences=[W[2], W[3], W[4], B[2]])
        
        [h21, c21, h22, c22], updates = theano.scan(
            fn=LSTM2Layer,
            sequences=[statex2, x2_mask],
            truncate_gradient=self.truncate,
            outputs_info=[dict(initial=h11[-1]),  #using h[end] to initialize the second LSTM
                          dict(initial=T.zeros([self.batchSize, self.hiddenDim])),
                          dict(initial=h12[-1]),
                          dict(initial=T.zeros([self.batchSize, self.hiddenDim]))],
            non_sequences=[W[5], W[6], W[7], B[3]])
       
        #predict
        _s = T.nnet.softmax(h12[-1].dot(V[0]) + h22[-1].dot(V[1]) + b)
        _p = T.argmax(_s, axis=1)
        _c = T.nnet.categorical_crossentropy(_s, y)
        _l = T.sum(E**2) + T.sum(W**2) + T.sum(B**2)
        cost = T.sum(_c) + 0.01 * _l
        
        # Gradients
        dE = T.grad(cost, E)
        dW = T.grad(cost, W)
        dB = T.grad(cost, B)
        dV = T.grad(cost, V)
        db = T.grad(cost, b)
        
        # Assign functions
        self.bptt        = theano.function([x1, x2, x1_mask, x2_mask, y], [dE, dW, dB, dV, db])
        self.errors      = theano.function([x1, x2, x1_mask, x2_mask, y], _c)
        self.weights     = theano.function([x1, x2, x1_mask, x2_mask], _s)
        self.predictions = theano.function([x1, x2, x1_mask, x2_mask], _p)
        
        # SGD parameters
        learningRate  = T.scalar('learningRate')
        decay         = T.scalar('decay')
        
        # rmsprop cache updates
        mE = decay * self.mE + (1 - decay) * dE ** 2
        mW = decay * self.mW + (1 - decay) * dW ** 2
        mB = decay * self.mB + (1 - decay) * dB ** 2
        mV = decay * self.mV + (1 - decay) * dV ** 2
        mb = decay * self.mb + (1 - decay) * db ** 2
        
        self.sgd_step = theano.function(
            [x1, x2, x1_mask, x2_mask, y, learningRate, decay], #theano.In(decay, value=0.9)],
            [], 
            updates=[
                     (E, E - learningRate * dE / T.sqrt(mE + 1e-6)),
                     (W, W - learningRate * dW / T.sqrt(mW + 1e-6)),
                     (B, B - learningRate * dB / T.sqrt(mB + 1e-6)),
                     (V, V - learningRate * dV / T.sqrt(mV + 1e-6)),
                     (b, b - learningRate * db / T.sqrt(mb + 1e-6)),
                     (self.mE, mE),
                     (self.mW, mW),
                     (self.mB, mB),
                     (self.mV, mV),
                     (self.mb, mb)
            ])
        #basic sgd method
        self.sgd_step_basic = theano.function(
            [x1, x2, x1_mask, x2_mask, y, learningRate],
            [],
            updates=[
                (E, E - learningRate * dE),
                (W, W - learningRate * dW),
                (B, B - learningRate * dB),
                (V, V - learningRate * dV),
                (b, b - learningRate * db)
            ])

    #save paramenters
    def save_model(self, outfile):
        np.savez(outfile,
            E = self.E.get_value(),
            W = self.W.get_value(),
            B = self.B.get_value(),
            V = self.V.get_value(),
            b = self.b.get_value())
        print "Saved LSTM2 parameters to %s." % outfile

    def load_model(self, path):
        npzfile = np.load(path)
        E, W, B, V, b = npzfile["E"], npzfile["W"], npzfile["B"], npzfile["V"], npzfile["b"]
        self.hiddenDim, self.wordDim, self.classDim = E.shape[1], E.shape[0], V.shape[2]
        print "Loading model from %s.\nParamenters: \t|classDim=%d \t|hiddenDim=%d \t|wordDim=%d" % (path, self.classDim, self.hiddenDim, self.wordDim)
        sys.stdout.flush()
        self.E.set_value(E)
        self.W.set_value(W)
        self.B.set_value(B)
        self.V.set_value(V)
        self.b.set_value(b)
