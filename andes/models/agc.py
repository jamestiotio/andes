from cvxopt import matrix, spmatrix
from cvxopt import mul, div, exp
from ..consts import *
from .base import ModelBase
from ..utils.math import zeros


class ACE(ModelBase):
    def __init__(self, system, name):
        super(ACE, self).__init__(system, name)
        self._group = 'Calculation'
        self._data.update({'area': None,
                           })
        self._mandatory.extend(['area'])
        self._algebs.extend(['e'])
        self.calls.update({'gcall': True, 'init1': True,
                           'jac0': True,
                           })
        self._service.extend(['P0', 'Q0'])
        self._fnamey.extend(['\epsilon'])
        self._init()

    def init1(self, dae):
        self.copy_data_ext('Area', field='area_P0', dest='P0', idx=self.area)
        self.copy_data_ext('Area', field='area_Q0', dest='Q0', idx=self.area)

    def gcall(self, dae):
        P = self.read_data_ext('Area', field='area_P0', idx=self.area)

        dae.g[self.e] = dae.y[self.e] - (P - self.P0)

    def jac0(self, dae):
        dae.add_jac(Gy0, 1, self.e, self.e)


class AGC(ModelBase):
    def __init__(self, system, name):
        super(AGC, self).__init__(system, name)
        self._group = 'Control'
        self._data.update({'coi': None,
                           'ace': None,
                           'beta': 0,
                           'Ki': 0,
                           'coi_measure': None,
                           })
        self._params.extend(['beta', 'Ki'])
        self._algebs.extend(['ACE'])
        self._states.extend(['AGC'])
        self._fnamey.extend(['ACE'])
        self._fnamex.extend(['AGC'])

        self._mandatory.extend(['coi', 'ace'])
        self.calls.update({'init1': True, 'gcall': True,
                           'jac0': True, 'fcall': True,

                           })
        self._service.extend(['pm'])
        self._init()

    def init1(self, dae):
        self.pm = [[]] * self.n
        self.copy_data_ext('ACE', field='e', idx=self.ace)
        self.copy_data_ext('COI', field='syn', idx=self.coi)
        self.copy_data_ext('COI', field='omega', dest='comega', idx=self.coi_measure)
        self.copy_data_ext('COI', field='M', dest='M', idx=self.coi)
        self.copy_data_ext('COI', field='Mtot', dest='Mtot', idx=self.coi)
        for idx in range(self.n):
            self.pm[idx] = self.read_data_ext('Synchronous', field='pm', idx=self.syn[idx])

    def gcall(self, dae):
        dae.g[self.ACE] = -mul(self.beta, (dae.y[self.comega] - 1)) - dae.y[self.e] - dae.y[self.ACE]
        for idx in range(self.n):
            dae.g[self.pm[idx]] -= div(self.M[idx], self.Mtot[idx]) * dae.x[self.AGC[idx]]

    def fcall(self, dae):
        dae.f[self.AGC] = mul(self.Ki, dae.y[self.ACE])

    def jac0(self, dae):
        dae.add_jac(Gy0, -1, self.ACE, self.ACE)
        dae.add_jac(Gy0, - self.beta, self.ACE, self.comega)
        dae.add_jac(Gy0, -1, self.ACE, self.e)

        dae.add_jac(Fy0, self.Ki, self.AGC, self.ACE)

    def gycall(self, dae):
        for idx in range(self.n):
            dae.add_jac(Gx, -div(self.M[idx], self.Mtot[idx]), self.pm[idx], self.AGC[idx])


class EAGC(ModelBase):
    def __init__(self, system, name):
        super(EAGC, self).__init__(system, name)
        self._group = 'Control'
        self._data.update({'cl': None,
                           'tl': 0.,
                           'Pl': None,
                           'agc': None
                           })
        self._descr.update({'cl': 'Loss sharing coefficient (vector)',
                            'tl': 'Time of generator loss',
                            'Pl': 'Loss of power generation in pu (vector)'})
        self.calls.update({'gcall': True, 'init1': True})
        # self._algebs.extend(['Pmod'])
        # self._fnamey.extend(['P_{mod}'])
        self._mandatory.extend(['cl', 'tl', 'Pl', 'agc'])
        self._service.extend(['en', 'pm', 'M', 'Mtot'])

        self._init()

    def init1(self, dae):
        self.pm = [[]] * self.n
        self.M = [[]] * self.n
        self.Mtot = [[]] * self.n
        for idx, item in enumerate(self.agc):
            self.pm[idx] = self.read_data_ext('AGC', field='pm', idx=item)
            self.M[idx] = self.read_data_ext('AGC', field='M', idx=item)
            self.Mtot[idx] = self.read_data_ext('AGC', field='Mtot', idx=item)

        # self.copy_data_ext('AGC', src='Mtot', fkey=self.agc)

        # self.en = matrix(0, (self.n, 1), 'd')
        self.en = zeros(self.n, 1)

    def switch(self):
        """Switch if time for n has come"""
        t = self.system.DAE.t
        for idx in range(self.n):
            if t >= self.tl[idx]:
                if self.en[idx] == 0:
                    self.en[idx] = 1
                    self.system.Log.info('EAGC <{}> activated at t = {:4} s'.format(idx, t))

    def gcall(self, dae):
        self.switch()
        Pmod = [0] * self.n
        for idx in range(self.n):
            Pmod[idx] = mul(self.en[idx], matrix(self.Pl[idx]) - matrix(self.cl[idx]) * sum(self.Pl[idx]))
            for area in range(len(Pmod[idx])):
                dae.g[self.pm[idx][area]] -= mul(div(self.M[idx][area], self.Mtot[idx][area]), Pmod[idx][area])


# class EAGC(ModelBase):
#     def __init__(self, system, name):
#         super(EAGC, self).__init__(system, name)
#         self._data.update({'coi': None,
#                            'ace': None,
#                            'beta': 0,
#                            'Ki': 0,
#                            'cl': None,
#                            'Pl': None,
#                            'tl': None,
#                            })
#         self._params.extend(['beta', 'Ki'])
#         self._algebs.extend(['ACE', 'Pmod'])
#         self._states.extend(['AGC'])
#         self._fnamey.extend(['ACE', 'P_{mod}'])
#         self._fnamex.extend(['AGC'])
#
#         self._mandatory.extend(['coi', 'ace', 'cl', 'Pl', 'tl'])
#         self.calls.update({'init1': True, 'gcall': True,
#                            'jac0': True, 'fcall': True,
#                            })
#         self._service.extend(['pm', 'en'])
#         self._init()
#
#     def init1(self, dae):
#         self.pm = [[]] * self.n
#         self.copy_data_ext('ACE', src='e', fkey=self.ace)
#         self.copy_data_ext('COI', src='syn', fkey=self.coi)
#         self.copy_data_ext('COI', src='omega', dest='comega', fkey=self.coi)
#         self.copy_data_ext('COI', src='M', dest='M', fkey=self.coi)
#         self.copy_data_ext('COI', src='Mtot', dest='Mtot', fkey=self.coi)
#         for idx in range(self.n):
#             self.pm[idx] = self.read_data_ext('Synchronous', src='pm', fkey=self.syn[idx])
#
#
#     def gcall(self, dae):
#         self.switch()
#         dae.g[self.ACE] = -mul(self.beta, (dae.y[self.comega] - 1)) - dae.y[self.e] - dae.y[self.ACE]
#         for idx in range(self.n):
#             dae.g[self.Pmod[idx]] = mul(self.en, self.Pl[idx] - self.cl[idx] * sum(self.Pl[idx])) - dae.y[self.Pmod[i]]
#             dae.g[self.pm[idx]] -= div(self.M[idx], self.Mtot[idx]) * dae.x[self.AGC[idx]] + dae.y[self.Pmod[i]]
#
#     def switch(self):
#         """Switch if time for n has come"""
#         for idx in range(self.n):
#             if self.system.DAE.t >= self.tl[idx]:
#                 self.en[idx] = 1
#
#     def fcall(self, dae):
#         dae.f[self.AGC] = mul(self.Ki, dae.y[self.ACE])
#
#     def jac0(self, dae):
#         dae.add_jac(Gy0, -1, self.ACE, self.ACE)
#         dae.add_jac(Gy0, - self.beta, self.ACE, self.comega)
#         dae.add_jac(Gy0, -1, self.ACE, self.e)
#
#         dae.add_jac(Gy0, -1, self.Pmod, self.Pmod)
#
#         dae.add_jac(Fy0, self.Ki, self.AGC, self.ACE)
#
#     def gycall(self, dae):
#         for idx in range(self.n):
#             dae.add_jac(Gx, -div(self.M[idx], self.Mtot[idx]), self.pm[idx], self.AGC[idx])
