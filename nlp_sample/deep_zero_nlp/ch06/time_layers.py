from typing import Optional, Tuple

import numpy as np

from functions import sigmoid, softmax
from layers import Embedding


class LSTM:
    def __init__(self, Wx: np.ndarray, Wh: np.ndarray, b: np.ndarray) -> None:
        self.params = [Wx, Wh, b]
        self.grads = [np.zeros_like(Wx), np.zeros_like(Wh), np.zeros_like(b)]
        self.cache = None

    def forward(self, x: np.ndarray, h_prev: np.ndarray, c_prev: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        Wx, Wh, b = self.params
        _, H = h_prev.shape

        A = np.dot(x, Wx) + np.dot(h_prev, Wh) + b

        f = A[:, :H]
        g = A[:, H:2*H]
        i = A[:, 2*H:3*H]
        o = A[:, 3*H:]

        f = sigmoid(f)
        g = np.tanh(g)
        i = sigmoid(f)
        o = sigmoid(o)

        c_next = f * c_prev + g * i
        h_next = o * np.tanh(c_next)

        self.cache = (x, h_prev, c_prev, i, f, g, o, c_next)
        return h_next, c_next

    def backward(self, dh_next: np.ndarray, dc_next: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        Wx, Wh, _ = self.params
        x, h_prev, c_prev, i, f, g, o, c_next = self.cache

        tanh_c_next = np.tanh(c_next)

        ds = dc_next + (dh_next*o) * (1 - tanh_c_next ** 2)
        dc_prev = ds*f

        di = ds * g
        df = ds * c_prev
        do = dh_next * tanh_c_next
        dg = ds * i

        di *= i*(1-i)
        df *= f*(1-f)
        do *= o*(1-o)
        dg *= (1 - g**2)

        dA = np.hstack((df, dg, di, do))

        dWh = np.dot(h_prev.T, dA)
        dWx = np.dot(x.T, dA)
        db = dA.sum(axis=0)

        self.grads[0][...] = dWx
        self.grads[1][...] = dWh
        self.grads[2][...] = db

        dx = np.dot(dA, Wx.T)
        dh_prev = np.dot(dA, Wh.T)

        return dx, dh_prev, dc_prev


class TimeLSTM:
    def __init__(self, Wx: np.ndarray, Wh: np.ndarray, b: np.ndarray, stateful: bool=False) -> None:
        self.params = [Wx, Wh, b]
        self.grads = [np.zeros_like(Wx), np.zeros_like(Wh), np.zeros_like(b)]
        self.layers = None
        self.h, self.c = None, None
        self.dh = None
        self.stateful = stateful

    def forward(self, xs: np.ndarray) -> np.ndarray:
        _, Wh, _ = self.params
        N, T, _ = xs.shape
        H = Wh.shape[0]

        self.layers = []
        hs = np.empty((N, T, H), dtype=float)

        if not self.stateful or self.h is None:
            self.h = np.zeros((N, H), dtype=float)
        if not self.stateful or self.c is None:
            self.c = np.zeros((N, H), dtype=float)
        
        for t in range(T):
            layer = LSTM(*self.params)
            self.h, self.c = layer.forward(xs[:, t, :], self.h, self.c)
            hs[:, t, :] = self.h
            
            self.layers.append(layer)
        
        return hs

    def backward(self, dhs: np.ndarray) -> np.ndarray:
        Wx, _, _ = self.params
        N, T, _ = dhs.shape
        D = Wx.shape[0]

        dxs = np.empty((N, T, D), dtype=float)
        dh, dc = 0, 0

        grads = [0, 0, 0]
        for t in reversed(range(T)):
            layer = self.layers[t]
            dx, dh, dc = layer.backward(dhs[:, t, :]+dh, dc)
            dxs[:, t, :] = dx
            for i, grad in enumerate(layer.grads):
                grads[i] += grad
        
        for i, grad in enumerate(grads):
            self.grads[i][...] = grad
        self.dh = dh
        return dxs

    def set_state(self, h: np.ndarray, c: Optional[np.ndarray]=None) -> None:
        self.h, self.c = h, c

    def reset_state(self) -> None:
        self.h, self.c = None, None


class TimeEmbedding:
    def __init__(self, W: np.ndarray) -> None:
        self.params = [W]
        self.grads = [np.zeros_like(W)]
        self.layers = None
        self.W = W

    def forward(self, xs: np.ndarray) -> np.ndarray:
        N, T = xs.shape
        _, D = self.W.shape

        out = np.empty((N, T, D), dtype=float)
        self.layers = []

        for t in range(T):
            layer = Embedding(self.W)
            out[:, t, :] = layer.forward(xs[:, t])
            self.layers.append(layer)
        
        return out

    def backward(self, dout: np.ndarray) -> None:
        _, T, _ = dout.shape

        grad = 0
        for t in range(T):
            layer = self.layers[t]
            layer.backward(dout[:, t, :])
            grad += layer.grads[0]
        
        self.grads[0][...] = grad
        return None


class TimeAffine:
    def __init__(self, W: np.ndarray, b: np.ndarray) -> None:
        self.params = [W, b]
        self.grads = [np.zeros_like(W), np.zeros_like(b)]
        self.x = None

    def forward(self, x: np.ndarray) -> np.ndarray:
        N, T, _ = x.shape
        W, b = self.params

        rx = x.reshape(N*T, -1)
        out = np.dot(rx, W) + b
        self.x = x
        return out.reshape(N, T, -1)

    def backward(self, dout: np.ndarray) -> np.ndarray:
        x = self.x
        N, T, _ = x.shape
        W, _ = self.params

        dout = dout.reshape(N*T, -1)
        rx = x.reshape(N*T, -1)

        db = np.sum(dout, axis=0)
        dW = np.dot(rx.T, dout)
        dx = np.dot(dout, W.T)
        dx = dx.reshape(*x.shape)

        self.grads[0][...] = dW
        self.grads[1][...] = db
        return dx


class TimeSoftmaxWithLoss:
    def __init__(self) -> None:
        self.params, self.grads = [], []
        self.cache = None
        self.ignore_label = -1

    def forward(self, xs: np.ndarray, ts: np.ndarray) -> float:
        N, T, V = xs.shape

        if ts.ndim == 3:
            ts = ts.argmax(axis=2)
        
        mask = (ts != self.ignore_label)

        xs = xs.reshape(N*T, V)
        ts = ts.reshape(N*T)
        mask = mask.reshape(N*T)

        ys = softmax(xs)
        ls = np.log(ys[np.arange(N*T), ts])
        ls *= mask
        loss = -np.sum(ls)
        loss /= mask.sum()

        self.cache = (ts, ys, mask, (N, T, V))
        return loss

    def backward(self, dout: float=1) -> np.ndarray:
        ts, ys, mask, (N, T, V) = self.cache

        dx = ys
        dx[np.arange(N*T), ts] -= 1
        dx *= dout
        dx /= mask.sum()
        dx *= mask[:, np.newaxis]

        dx = dx.reshape((N, T, V))
        return dx


class TimeDropout:
    def __init__(self, dropout_ratio: float=0.5) -> None:
        self.params, self.grads = [], []
        self.dropout_ratio = dropout_ratio
        self.mask = None
        self.train_flg = True

    def forward(self, xs: np.ndarray) -> np.ndarray:
        if self.train_flg:
            flg = np.random.rand(*xs.shape) > self.dropout_ratio
            scale = 1.0 / (1.0 - self.dropout_ratio)
            self.mask = flg.astype(np.float32) * scale
            return xs * self.mask
        else:
            return xs

    def backward(self, dout: float) -> np.ndarray:
        return dout * self.mask
