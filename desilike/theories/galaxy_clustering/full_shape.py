import re

import numpy as np
from scipy import interpolate

from desilike.jax import numpy as jnp
from desilike import utils
from .base import BaseTheoryPowerSpectrumMultipolesFromWedges
from .base import BaseTheoryPowerSpectrumMultipoles, BaseTheoryCorrelationFunctionMultipoles, BaseTheoryCorrelationFunctionFromPowerSpectrumMultipoles
from .power_template import DirectPowerSpectrumTemplate, StandardPowerSpectrumTemplate


class BasePTPowerSpectrumMultipoles(BaseTheoryPowerSpectrumMultipoles):

    """Base class for perturbation theory matter power spectrum multipoles."""
    _default_options = dict()

    def initialize(self, *args, template=None, **kwargs):
        self.options = self._default_options.copy()
        for name, value in self._default_options.items():
            self.options[name] = kwargs.pop(name, value)
        super(BasePTPowerSpectrumMultipoles, self).initialize(*args, **kwargs)
        if template is None:
            template = DirectPowerSpectrumTemplate()
        self.template = template
        kin = np.geomspace(min(1e-3, self.k[0] / 2, self.template.init.get('k', [1.])[0]), max(1., self.k[-1] * 2, self.template.init.get('k', [0.])[0]), 3000)  # margin for AP effect
        self.template.init.update(k=kin)


class BasePTCorrelationFunctionMultipoles(BaseTheoryCorrelationFunctionMultipoles):

    _default_options = dict()

    def initialize(self, *args, template=None, **kwargs):
        self.options = self._default_options.copy()
        for name, value in self._default_options.items():
            self.options[name] = kwargs.pop(name, value)
        super(BasePTCorrelationFunctionMultipoles, self).initialize(*args, **kwargs)
        if template is None:
            template = DirectPowerSpectrumTemplate()
        self.template = template
        kin = np.geomspace(min(1e-3, 1 / self.s[-1] / 2, self.template.init.get('k', [1.])[0]), max(2., 1 / self.s[0] * 2, self.template.init.get('k', [0.])[0]), 3000)  # margin for AP effect
        self.template.init.update(k=kin)


class BaseTracerPowerSpectrumMultipoles(BaseTheoryPowerSpectrumMultipoles):

    """Base class for perturbation theory tracer power spectrum multipoles."""
    config_fn = 'full_shape.yaml'
    _default_options = dict()

    def initialize(self, *args, pt=None, template=None, **kwargs):
        self.options = self._default_options.copy()
        for name, value in self._default_options.items():
            self.options[name] = kwargs.pop(name, value)
        if pt is None:
            pt = globals()[getattr(self, 'pt_cls', self.__class__.__name__.replace('Tracer', ''))]()
        self.pt = pt
        if template is not None:
            self.pt.init.update(template=template)
        for name, value in self.pt._default_options.items():
            if name in kwargs:
                self.pt.init.update({name: kwargs.pop(name)})
            elif name in self.options:
                self.pt.init.update({name: self.options[name]})
        for name in ['method', 'mu']:
            if name in kwargs:
                self.pt.init.update({name: kwargs.pop(name)})
        self.required_bias_params, self.optional_bias_params = {}, {}
        super(BaseTracerPowerSpectrumMultipoles, self).initialize(*args, **kwargs)
        self.pt.init.update(k=self.k, ells=self.ells)
        self.set_params()

    def set_params(self):
        self.pt.params.update(self.params.select(basename=self.pt.params.basenames()))
        self.params = self.params.select(basename=list(self.required_bias_params.keys()) + list(self.optional_bias_params.keys()))

    def get(self):
        return self.power

    @property
    def template(self):
        return self.pt.template


class BaseTracerCorrelationFunctionMultipoles(BaseTheoryCorrelationFunctionMultipoles):

    """Base class for perturbation theory tracer correlation function multipoles."""
    config_fn = 'full_shape.yaml'
    _default_options = dict()

    def initialize(self, *args, pt=None, template=None, **kwargs):
        self.options = self._default_options.copy()
        for name, value in self._default_options.items():
            self.options[name] = kwargs.pop(name, value)
        if pt is None:
            pt = globals()[getattr(self, 'pt_cls', self.__class__.__name__.replace('Tracer', ''))]()
        self.pt = pt
        if template is not None:
            self.pt.init.update(template=template)
        for name, value in self.pt._default_options.items():
            if name in kwargs:
                self.pt.init.update({name: kwargs.pop(name)})
            elif name in self.options:
                self.pt.init.update({name: self.options[name]})
        self.required_bias_params, self.optional_bias_params = {}, {}
        super(BaseTracerCorrelationFunctionMultipoles, self).initialize(*args, **kwargs)
        self.pt.init.update(s=self.s, ells=self.ells)
        self.set_params()

    def set_params(self):
        self.pt.params.update(self.params.select(basename=self.pt.params.basenames()))
        self.params = self.params.select(basename=list(self.required_bias_params.keys()) + list(self.optional_bias_params.keys()))

    def get(self):
        return self.corr

    @property
    def template(self):
        return self.pt.template


class BaseTracerCorrelationFunctionFromPowerSpectrumMultipoles(BaseTheoryCorrelationFunctionFromPowerSpectrumMultipoles):

    """Base class for perturbation theory tracer correlation function multipoles as Hankel transforms of the power spectrum multipoles."""
    config_fn = 'full_shape.yaml'

    def initialize(self, *args, pt=None, template=None, **kwargs):
        power = globals()[self.__class__.__name__.replace('CorrelationFunction', 'PowerSpectrum')]()
        if pt is not None: power.init.update(pt=pt)
        if template is not None: power.init.update(template=template)
        super(BaseTracerCorrelationFunctionFromPowerSpectrumMultipoles, self).initialize(*args, power=power, **kwargs)

    @property
    def pt(self):
        return self.power.pt

    @property
    def template(self):
        return self.power.template

    def get(self):
        return self.corr


class SimpleTracerPowerSpectrumMultipoles(BasePTPowerSpectrumMultipoles, BaseTheoryPowerSpectrumMultipolesFromWedges):
    r"""
    Kaiser tracer power spectrum multipoles, with fixed damping, essentially used for Fisher forecasts.

    Parameters
    ----------
    k : array, default=None
        Theory wavenumbers where to evaluate multipoles.

    ells : tuple, default=(0, 2, 4)
        Multipoles to compute.

    mu : int, default=8
        Number of :math:`\mu`-bins to use (in :math:`[0, 1]`).

    template : BasePowerSpectrumTemplate
        Power spectrum template. Defaults to :class:`StandardPowerSpectrumTemplate`.
    """
    config_fn = 'full_shape.yaml'

    def initialize(self, *args, mu=8, method='leggauss', template=None, **kwargs):
        if template is None:
            template = StandardPowerSpectrumTemplate()
        super(SimpleTracerPowerSpectrumMultipoles, self).initialize(*args, template=template, mu=mu, method=method, **kwargs)

    def calculate(self, b1=1., sn0=0., sigmapar=0., sigmaper=0.):
        jac, kap, muap = self.template.ap_k_mu(self.k, self.mu)
        f = self.template.f
        sigmanl2 = self.k[:, None]**2 * (sigmapar**2 * self.mu**2 + sigmaper**2 * (1. - self.mu**2))
        damping = np.exp(-sigmanl2 / 2.)
        #pkmu = jac * damping * (b1 + f * muap**2)**2 * jnp.interp(jnp.log10(kap), jnp.log10(self.template.k), self.template.pk_dd) + sn0
        pkmu = jac * damping * (b1 + f * muap**2)**2 * interpolate.InterpolatedUnivariateSpline(np.log10(self.template.k), self.template.pk_dd, k=3, ext=2)(np.log10(kap)) + sn0
        self.power = self.to_poles(pkmu)

    def get(self):
        return self.power


class KaiserPowerSpectrumMultipoles(BasePTPowerSpectrumMultipoles, BaseTheoryPowerSpectrumMultipolesFromWedges):
    r"""
    Kaiser power spectrum multipoles.

    Parameters
    ----------
    k : array, default=None
        Theory wavenumbers where to evaluate multipoles.

    ells : tuple, default=(0, 2, 4)
        Multipoles to compute.

    mu : int, default=8
        Number of :math:`\mu`-bins to use (in :math:`[0, 1]`).

    template : BasePowerSpectrumTemplate
        Power spectrum template. Defaults to :class:`DirectPowerSpectrumTemplate`.
    """
    _params = {'sigmapar': {'value': 0., 'fixed': True}, 'sigmaper': {'value': 0, 'fixed': True}}

    def initialize(self, *args, mu=8, **kwargs):
        super(KaiserPowerSpectrumMultipoles, self).initialize(*args, mu=mu, method='leggauss', **kwargs)
        #self.template.init.update(k=np.logspace(-4, 2, 1000))

    def calculate(self, sigmapar=0., sigmaper=0.):
        jac, kap, muap = self.template.ap_k_mu(self.k, self.mu)
        f = self.template.f
        sigmanl2 = kap**2 * (sigmapar**2 * muap**2 + sigmaper**2 * (1. - muap**2))
        damping = np.exp(-sigmanl2 / 2.)

        self.pktable = []
        self.k11 = self.template.k
        self.pk11 = self.template.pk_dd
        pktable = jac * damping * interpolate.interp1d(np.log10(self.k11), self.pk11, kind='cubic', axis=-1)(np.log10(kap))
        self.pktable = {'pk_dd': self.to_poles(pktable), 'pk_dt': self.to_poles(f * muap**2 * pktable), 'pk_tt': self.to_poles(f**2 * muap**4 * pktable)}
        self.pktable['pk11'] = self.pktable['pk_dd']

    def __getstate__(self):
        state = {}
        for name in ['k', 'z', 'ells']:
            if hasattr(self, name):
                state[name] = getattr(self, name)
        for name in self.pktable:
            state[name] = self.pktable[name]
        state['names'] = list(self.pktable.keys())
        return state

    def __setstate__(self, state):
        state = dict(state)
        self.pktable = {name: state.pop(name, None) for name in state['names']}
        super(KaiserPowerSpectrumMultipoles, self).__setstate__(state)


class KaiserTracerPowerSpectrumMultipoles(BaseTracerPowerSpectrumMultipoles):
    r"""
    Kaiser tracer power spectrum multipoles.

    Parameters
    ----------
    k : array, default=None
        Theory wavenumbers where to evaluate multipoles.

    ells : tuple, default=(0, 2, 4)
        Multipoles to compute.

    mu : int, default=8
        Number of :math:`\mu`-bins to use (in :math:`[0, 1]`).

    template : BasePowerSpectrumTemplate
        Power spectrum template. Defaults to :class:`DirectPowerSpectrumTemplate`.
    """
    def set_params(self):
        self.required_bias_params.update(dict(b1=1., sn0=0))
        super(KaiserTracerPowerSpectrumMultipoles, self).set_params()

    def calculate(self, b1=1., sn0=0.):
        sn0 = np.array([(ell == 0) for ell in self.ells], dtype='f8')[:, None] * sn0
        self.power = b1**2 * self.pt.pktable['pk_tt'] + 2. * b1 * self.pt.pktable['pk_dt'] + self.pt.pktable['pk_tt'] + sn0


class KaiserTracerCorrelationFunctionMultipoles(BaseTracerCorrelationFunctionFromPowerSpectrumMultipoles):
    r"""
    Kaiser tracer correlation function multipoles.

    Parameters
    ----------
    s : array, default=None
        Theory separations where to evaluate multipoles.

    ells : tuple, default=(0, 2, 4)
        Multipoles to compute.

    template : BasePowerSpectrumTemplate
        Power spectrum template. Defaults to :class:`DirectPowerSpectrumTemplate`.

    **kwargs : dict
        Options, defaults to: ``mu=8``.
    """


class BaseEFTLikeTracerPowerSpectrumMultipoles(object):
    r"""
    Base class for tracer power spectrum multipoles with EFT-like counter and stochastic terms.
    Can be exactly marginalized over counter terms and stochastic terms ct*, sn*.
    """
    def initialize(self, *args, **kwargs):
        self.pt_cls = self.__class__.__name__.replace('EFTLike', '').replace('Tracer', '')
        super(BaseEFTLikeTracerPowerSpectrumMultipoles, self).initialize(*args, **kwargs)

    def set_params(self):
        self.kp = 1.

        def get_params_matrix(base):
            coeffs = {ell: {} for ell in self.ells}
            for param in self.params.select(basename=base + '*_*'):
                name = param.basename
                match = re.match(base + '(.*)_(.*)', name)
                if match:
                    ell, pow = int(match.group(1)), int(match.group(2))
                    if ell in self.ells:
                        coeffs[ell][name] = (self.k / self.kp)**pow
                    else:
                        del self.params[param]
            for param in self.params.select(basename=base + '0'):
                ell, name = 0, param.basename
                if ell in self.ells:
                    if name + '_0' in coeffs[ell]:
                        raise ValueError('Choose between {} and {}'.format(name, name + '_0'))
                    coeffs[ell][name] = 1.
                else:
                    del self.params[param]
            params = [name for ell in self.ells for name in coeffs[ell]]
            if not params:
                return params, jnp.array([], dtype='f8')
            matrix = []
            for ell in self.ells:
                row = [np.zeros_like(self.k) for i in range(len(params))]
                for name, k_i in coeffs[ell].items():
                    row[params.index(name)][:] = k_i
                matrix.append(np.column_stack(row))
            matrix = jnp.array(matrix)
            return params, matrix

        self.counterterm_params, self.counterterm_matrix = get_params_matrix('ct')
        self.stochastic_params, self.stochastic_matrix = get_params_matrix('sn')
        params = self.counterterm_params + self.stochastic_params
        self.required_bias_params = dict(**self.required_bias_params, **dict(zip(params, [0] * len(params))))
        super(BaseEFTLikeTracerPowerSpectrumMultipoles, self).set_params()

    def calculate(self, **params):
        counterterm_values = jnp.array([params.pop(name, 0.) for name in self.counterterm_params])
        stochastic_values = jnp.array([params.pop(name, 0.) for name in self.stochastic_params])
        super(BaseEFTLikeTracerPowerSpectrumMultipoles, self).calculate(**params)
        self.power += self.counterterm_matrix.dot(counterterm_values) * self.pt.pktable['pk11'][self.pt.ells.index(0)]
        self.power += self.stochastic_matrix.dot(stochastic_values)


class EFTLikeKaiserTracerPowerSpectrumMultipoles(BaseEFTLikeTracerPowerSpectrumMultipoles, KaiserTracerPowerSpectrumMultipoles):
    r"""
    Kaiser tracer power spectrum multipoles with EFT-like counter and stochastic terms.
    Can be exactly marginalized over counter terms and stochastic terms ct*, sn*.

    Parameters
    ----------
    k : array, default=None
        Theory wavenumbers where to evaluate multipoles.

    ells : tuple, default=(0, 2, 4)
        Multipoles to compute.

    mu : int, default=8
        Number of :math:`\mu`-bins to use (in :math:`[0, 1]`).

    template : BasePowerSpectrumTemplate
        Power spectrum template. Defaults to :class:`DirectPowerSpectrumTemplate`.
    """


class EFTLikeKaiserTracerCorrelationFunctionMultipoles(BaseTracerCorrelationFunctionFromPowerSpectrumMultipoles):
    r"""
    EFT-like Kaiser tracer correlation function multipoles.
    Can be exactly marginalized over counter terms and stochastic terms ct*, sn*.

    Parameters
    ----------
    s : array, default=None
        Theory separations where to evaluate multipoles.

    ells : tuple, default=(0, 2, 4)
        Multipoles to compute.

    template : BasePowerSpectrumTemplate
        Power spectrum template. Defaults to :class:`DirectPowerSpectrumTemplate`.

    **kwargs : dict
        Options, defaults to: ``mu=8``.
    """


class TNSPowerSpectrumMultipoles(BasePTPowerSpectrumMultipoles, BaseTheoryPowerSpectrumMultipolesFromWedges):
    r"""
    TNS power spectrum multipoles.

    Parameters
    ----------
    k : array, default=None
        Theory wavenumbers where to evaluate multipoles.

    ells : tuple, default=(0, 2, 4)
        Multipoles to compute.

    mu : int, default=8
        Number of :math:`\mu`-bins to use (in :math:`[0, 1]`).

    template : BasePowerSpectrumTemplate
        Power spectrum template. Defaults to :class:`DirectPowerSpectrumTemplate`.
    """
    _default_options = dict(nloop=1)

    def initialize(self, *args, mu=8, **kwargs):
        super(TNSPowerSpectrumMultipoles, self).initialize(*args, mu=mu, method='leggauss', **kwargs)
        self.nloop = int(self.options['nloop'])
        if self.nloop not in [1]:
            raise ValueError('nloop must be one of 1 (1-loop)')

    def calculate(self):
        jac, kap, muap = self.template.ap_k_mu(self.k, self.mu)
        f = self.template.f

        self.pktable = []
        # We could have a speed-up with FFTlog, see https://arxiv.org/pdf/1603.04405.pdf
        self.k11 = np.linspace(self.k[0] * 0.8, self.k[-1] * 1.2, int(len(self.k) * 1.4 + 0.5))
        k = self.k11[:, None]
        q = self.template.k
        wq = utils.weights_trapz(q)
        jq = q**2 * wq / (4. * np.pi**2)
        mus, wmus = utils.weights_mu(20, method='leggauss', sym=False)
        x = q / k
        # Kernel for P13
        if any(getattr(self, name, None) is None for name in ['kernel13_d, kernel13_t']):

            # Integral of F3(q, -q, k) over mu cosine angle between k and q
            def kernel_ff(x):
                toret = (6. / x**2 - 79. + 50. * x**2 - 21. * x**4 + 0.75 * (1. / x - x)**3 * (2. + 7. * x**2) * 2 * np.log(np.abs((x - 1.) / (x + 1.)))) / 504.
                mask = x > 10.
                toret[mask] = - 61. / 630. + 2. / 105. / x[mask]**2 - 10. / 1323. / x[mask]**4
                dx = x - 1.
                mask = np.abs(dx) < 0.01
                toret[mask] = - 11. / 126. + dx[mask] / 126. - 29. / 252. * dx[mask]**2
                return toret / x**2

            def kernel_gg(x):
                toret = (6. / x**2 - 41. + 2. * x**2 - 3. * x**4 + 0.75 * (1. / x - x)**3 * (2. + x**2) * 2 * np.log(np.abs((x - 1.) / (x + 1.)))) / 168.
                mask = x > 10.
                toret[mask] = - 3. / 10. + 26. / 245. / x[mask]**2 - 38. / 2205. / x[mask]**4
                dx = x - 1.
                mask = np.abs(dx) < 0.01
                toret[mask] = - 3. / 14. - 5. / 42. * dx[mask] - 1. / 84. * dx[mask]**2
                return toret / x**2

            self.kernel13_d = 2 * jq * kernel_ff(x)
            self.kernel13_t = 2 * jq * kernel_gg(x)

            def kernel_a(x):
                toret = np.zeros((5,) + x.shape, dtype='f8')
                logx = np.zeros_like(x)
                mask = np.abs(x - 1) > 1e-16
                logx[mask] = np.log(np.abs((x[mask] + 1) / (x[mask] - 1)))
                toret[0] = -1. / 84. / x * (2 * x * (19 - 24 * x**2 + 9 * x**4) - 9 * (x**2 - 1)**3 * logx)
                toret[1] = 1. / 112. / x**3 * (2 * x * (x**2 + 1) * (3 - 14 * x**2 + 3 * x**4) - 3 * (x**2 - 1)**4 * logx)
                toret[2] = 1. / 336. / x**3 * (2 * x * (9 - 185 * x**2 + 159 * x**4 - 63 * x**6) + 9 * (x**2 - 1)**3 * (7 * x**2 + 1) * logx)
                toret[4] = 1. / 336. / x**3 * (2 * x * (9 - 109 * x**2 + 63 * x**4 - 27 * x**6) + 9 * (x**2 - 1)**3 * (3 * x**2 + 1) * logx)

                mask = x < 1e-4
                xm = x[mask]
                toret[0][mask] = 8 * xm**8 / 735 + 24 * xm**6 / 245 - 24 * xm**4 / 35 + 8 * xm**2 / 7 - 2. / 3
                toret[1][mask] = - 16 * xm**8 / 8085 - 16 * xm**6 / 735 + 48 * xm**4 / 245 - 16 * xm**2 / 35
                toret[2][mask] = 32 * xm**8 / 1617 + 128 * xm**6 / 735 - 288 * xm**4 / 245 + 64 * xm**2 / 35 - 4. / 3
                toret[4][mask] = 24 * xm**8 / 2695 + 8 * xm**6 / 105 - 24 * xm**4 / 49 + 24 * xm**2 / 35 - 2. / 3

                mask = x > 1e2
                xm = x[mask]
                toret[0][mask] = 2. / 105 - 24 / (245 * xm**2) - 8 / (735 * xm**4) - 8 / (2695 * xm**6) - 8 / (7007 * xm**8)
                toret[1][mask] = -16. / 35 + 48 / (245 * xm**2) - 16 / (735 * xm**4) - 16 / (8085 * xm**6) - 16 / (35035 * xm**8)
                toret[2][mask] = -44. / 105 - 32 / (735 * xm**4) - 64 / (8085 * xm**6) - 96 / (35035 * xm**8)
                toret[4][mask] = -46. / 105 + 24 / (245 * xm**2) - 8 / (245 * xm**4) - 8 / (1617 * xm**6) - 8 / (5005 * xm**8)

                toret[3] = toret[1]
                return toret / x**2

            self.kernel_a = jq * kernel_a(x)

        # Compute P22
        self.pk22_dd, self.pk22_dt, self.pk22_tt = (0., ) * 3
        self.pk_b2d, self.pk_bs2d, self.pk_b2t, self.pk_bs2t, self.sig3sq, self.pk_b22, self.pk_b2s2, self.pk_bs22 = (0.,) * 8
        self.A = np.zeros((5,) + self.k11.shape, dtype='f8')
        self.B = np.zeros((12,) + self.k11.shape, dtype='f8')
        kernel_A, kernel_tA = (np.zeros((5,) + x.shape, dtype='f8') for i in range(2))
        pk_k = np.interp(self.k11, self.template.k, self.template.pk_dd)
        pk_q = self.template.pk_dd

        for mu, wmu in zip(mus, wmus):
            kdq = k * q * mu  # k \cdot q
            kq2 = k**2 - 2. * kdq + q**2  # |k - q|^2
            qdkq = kdq - q**2   # k \cdot (k - q)
            F2_d = 5. / 7. + 1. / 2. * qdkq * (1. / q**2 + 1. / kq2) + 2. / 7. * qdkq**2 / (q**2 * kq2)
            F2_t = 3. / 7. + 1. / 2. * qdkq * (1. / q**2 + 1. / kq2) + 4. / 7. * qdkq**2 / (q**2 * kq2)
            # https://arxiv.org/pdf/0902.0991.pdf
            S = (qdkq)**2 / (q**2 * kq2) - 1. / 3.
            D = 2. / 7. * (mu**2 - 1.)
            pk_kq = np.interp(kq2**0.5, self.template.k, self.template.pk_dd, left=0., right=0.)
            jq_pk_q_pk_kq = jq * pk_q * pk_kq
            self.pk_b2d += wmu * np.sum(jq_pk_q_pk_kq * F2_d, axis=-1)
            self.pk_bs2d += wmu * np.sum(jq_pk_q_pk_kq * F2_d * S, axis=-1)
            self.pk_b2t += wmu * np.sum(jq_pk_q_pk_kq * F2_t, axis=-1)
            self.pk_bs2t += wmu * np.sum(jq_pk_q_pk_kq * F2_t * S, axis=-1)
            self.sig3sq += wmu * np.sum(105. / 16. * jq * pk_q * (D * S + 8. / 63.), axis=-1)
            self.pk_b22 += wmu / 2. * np.sum(jq * pk_q * (pk_kq - pk_q), axis=-1)
            self.pk_b2s2 += wmu / 2. * np.sum(jq * pk_q * (pk_kq * S - 2. / 3. * pk_q), axis=-1)
            self.pk_bs22 += wmu / 2. * np.sum(jq * pk_q * (pk_kq * S**2 - 4. / 9. * pk_q), axis=-1)
            self.pk22_dd += 2 * wmu * np.sum(F2_d**2 * jq_pk_q_pk_kq, axis=-1)
            self.pk22_dt += 2 * wmu * np.sum(F2_d * F2_t * jq_pk_q_pk_kq, axis=-1)
            self.pk22_tt += 2 * wmu * np.sum(F2_t * F2_t * jq_pk_q_pk_kq, axis=-1)

            xmu = kq2 / k**2
            kernel_A[0] = - x**3 / 7. * (mu + 6 * mu**3 + x**2 * mu * (-3 + 10 * mu**2) + x * (-3 + mu**2 - 12 * mu**4))
            kernel_A[1] = x**4 / 14. * (mu**2 - 1) * (-1 + 7 * x * mu - 6 * mu**2)
            kernel_A[2] = x**3 / 14. * (x**2 * mu * (13 - 41 * mu**2) - 4 * (mu + 6 * mu**3) + x * (5 + 9 * mu**2 + 42 * mu**4))
            kernel_A[3] = kernel_A[1]
            kernel_A[4] = x**3 / 14. * (1 - 7 * x * mu + 6 * mu**2) * (-2 * mu + x * (-1 + 3 * mu**2))
            kernel_tA[0] = 1. / 7. * (mu + x - 2 * x * mu**2) * (3 * x + 7 * mu - 10 * x * mu**2)
            kernel_tA[1] = x / 14. * (mu**2 - 1) * (3 * x + 7 * mu - 10 * x * mu**2)
            kernel_tA[2] = 1. / 14. * (28 * mu**2 + x * mu * (25 - 81 * mu**2) + x**2 * (1 - 27 * mu**2 + 54 * mu**4))
            kernel_tA[3] = x / 14. * (1 - mu**2) * (x - 7 * mu + 6 * x * mu**2)
            kernel_tA[4] = 1. / 14. * (x - 7 * mu + 6 * x * mu**2) * (-2 * mu - x + 3 * x * mu**2)
            # Taruya 2010 (arXiv 1006.0699v1) eq A3
            self.A += wmu * np.sum(jq / x**2 * (kernel_A * pk_k[:, None] + kernel_tA * pk_q) * pk_kq / xmu**2, axis=-1)

            jq_pk_q_pk_kq /= x**2 * xmu
            self.B[0] += wmu * np.sum(x**2 * (mu**2 - 1.) / 2. * jq_pk_q_pk_kq, axis=-1)  # n,a,b = 1,1,1
            self.B[1] += wmu * np.sum(3. * x**2 * (mu**2 - 1.)**2 / 8. * jq_pk_q_pk_kq, axis=-1)  # n,a,b = 1,1,2
            self.B[2] += wmu * np.sum(3. * x**4 * (mu**2 - 1.)**2 / xmu / 8. * jq_pk_q_pk_kq, axis=-1)  # n,a,b = 1,2,1
            self.B[3] += wmu * np.sum(5. * x**4 * (mu**2 - 1.)**3 / xmu / 16. * jq_pk_q_pk_kq, axis=-1)  # n,a,b = 1,2,2
            self.B[4] += wmu * np.sum(x * (x + 2. * mu - 3. * x * mu**2) / 2. * jq_pk_q_pk_kq, axis=-1)  # n,a,b = 2,1,1
            self.B[5] += wmu * np.sum(- 3. * x * (mu**2 - 1.) * (-x - 2. * mu + 5. * x * mu**2) / 4. * jq_pk_q_pk_kq, axis=-1)  # n,a,b = 2,1,2
            self.B[6] += wmu * np.sum(3. * x**2 * (mu**2 - 1.) * (-2. + x**2 + 6. * x * mu - 5. * x**2 * mu**2) / xmu / 4. * jq_pk_q_pk_kq, axis=-1)  # n,a,b = 2,2,1
            self.B[7] += wmu * np.sum(- 3. * x**2 * (mu**2 - 1.)**2 * (6. - 5. * x**2 - 30. * x * mu + 35. * x**2 * mu**2) / xmu / 16. * jq_pk_q_pk_kq, axis=-1)  # n,a,b = 2,2,2
            self.B[8] += wmu * np.sum(x * (4. * mu * (3. - 5. * mu**2) + x * (3. - 30. * mu**2 + 35. * mu**4)) / 8. * jq_pk_q_pk_kq, axis=-1)  # n,a,b = 3,1,2
            self.B[9] += wmu * np.sum(x * (-8. * mu + x * (-12. + 36. * mu**2 + 12. * x * mu * (3. - 5. * mu**2) + x**2 * (3. - 30. * mu**2 + 35. * mu**4))) / xmu / 8. * jq_pk_q_pk_kq, axis=-1)  # n,a,b = 3,2,1
            self.B[10] += wmu * np.sum(3. * x * (mu**2 - 1.) * (-8. * mu + x * (-12. + 60. * mu**2 + 20. * x * mu * (3. - 7. * mu**2) + 5. * x**2 * (1. - 14. * mu**2 + 21. * mu**4))) / xmu / 16. * jq_pk_q_pk_kq, axis=-1)  # n,a,b = 3,2,2
            self.B[11] += wmu * np.sum(x * (8. * mu * (-3. + 5. * mu**2) - 6. * x * (3. - 30. * mu**2 + 35. * mu**4) + 6. * x**2 * mu * (15. - 70. * mu**2 + 63 * mu**4) + x**3 * (5. - 21. * mu**2 * (5. - 15. * mu**2 + 11. * mu**4))) / xmu / 16. * jq_pk_q_pk_kq, axis=-1)  # n,a,b = 4,2,2

        self.A += pk_k * np.sum(self.kernel_a * pk_q, axis=-1)
        self.pk11 = pk_k
        pk13_dd = 2. * np.sum(self.kernel13_d * self.template.pk_dd, axis=-1) * pk_k
        pk13_tt = 2. * np.sum(self.kernel13_t * self.template.pk_dd, axis=-1) * pk_k
        pk13_dt = (pk13_dd + pk13_tt) / 2.
        self.pk_sig3sq = self.sig3sq * pk_k
        self.pk_dd = self.pk11 + self.pk22_dd + pk13_dd
        self.pk_dt = self.pk11 + self.pk22_dt + pk13_dt
        self.pk_tt = self.pk11 + self.pk22_tt + pk13_tt

        names = ['pk11', 'pk_dd', 'pk_b2d', 'pk_bs2d', 'pk_sig3sq', 'pk_b22', 'pk_b2s2', 'pk_bs22', 'pk_dt', 'pk_b2t', 'pk_bs2t', 'pk_tt', 'A', 'B']
        pktable = np.vstack([getattr(self, name) for name in names])
        pktable = jac * interpolate.interp1d(np.log10(self.k11), pktable, kind='cubic', axis=-1)(np.log10(kap))
        A = pktable[12:]
        B = pktable[17:]
        #self._A = A
        #self._B = np.array([B[0], -(B[1] + B[2]), B[3], B[4], -(B[5] + B[6]), B[7], -(B[8] + B[9]), B[10], B[11]])
        A = np.array([f * A[0] * muap**2, f**2 * (A[1] * muap**2 + A[2] * muap**4), f**3 * (A[3] * muap**4 + A[4] * muap**6)])  # for b1^2, b1, 1
        B = np.array([f**2 * (B[0] * muap**2 + B[4] * muap**4),
                      -f**3 * ((B[1] + B[2]) * muap**2 + (B[5] + B[6]) * muap**4 + (B[8] + B[9]) * muap**6),
                      f**4 * (B[3] * muap**2 + B[7] * muap**4 + B[10] * muap**6 + B[11] * muap**8)])   # for b1^2, b1, 1

        pktable = [self.to_poles(pktable[:8, None]), self.to_poles(f * muap**2 * pktable[8:11, None]), self.to_poles(f**2 * muap**4 * pktable[11:12, None])]
        self.pktable = {}
        for pkt in pktable:
            for pk in pkt: self.pktable[names[len(self.pktable)]] = pk
        self.pktable['A'] = self.to_poles(A[:, None, ...])
        self.pktable['B'] = self.to_poles(B[:, None, ...])

    def __getstate__(self):
        state = {}
        for name in ['k', 'z', 'ells', 'nloop']:
            if hasattr(self, name):
                state[name] = getattr(self, name)
        for name in self.pktable:
            state[name] = self.pktable[name]
        state['names'] = list(self.pktable.keys())
        return state

    def __setstate__(self, state):
        state = dict(state)
        self.pktable = {name: state.pop(name, None) for name in state['names']}
        super(TNSPowerSpectrumMultipoles, self).__setstate__(state)


class TNSTracerPowerSpectrumMultipoles(BaseTracerPowerSpectrumMultipoles):
    r"""
    TNS tracer power spectrum multipoles.

    Parameters
    ----------
    k : array, default=None
        Theory wavenumbers where to evaluate multipoles.

    ells : tuple, default=(0, 2, 4)
        Multipoles to compute.

    mu : int, default=8
        Number of :math:`\mu`-bins to use (in :math:`[0, 1]`).

    template : BasePowerSpectrumTemplate
        Power spectrum template. Defaults to :class:`DirectPowerSpectrumTemplate`.
    """
    def set_params(self):
        self.required_bias_params.update(dict(b1=1., b2=0., bs=0., b3=0.))
        super(TNSTracerPowerSpectrumMultipoles, self).set_params()

    def calculate(self, b1=1., b2=0., bs=0., b3=0., sn0=0):
        self.power = b1**2 * self.pt.pktable['pk_dd'] + 2. * b1 * self.pt.pktable['pk_dt'] + self.pt.pktable['pk_tt'] + sn0
        bs2 = bs - 4. / 7. * (b1 - 1.)
        b3nl = b3 + 32. / 315. * (b1 - 1.)
        #bs2 = b3nl = 0.
        self.power += 2 * b1 * b2 * self.pt.pktable['pk_b2d'] + 2. * b1 * bs2 * self.pt.pktable['pk_bs2d']\
                      + 2 * b1 * b3nl * self.pt.pktable['pk_sig3sq'] + b2**2 * self.pt.pktable['pk_b22']\
                      + 2 * b2 * bs2 * self.pt.pktable['pk_b2s2'] + bs2**2 * self.pt.pktable['pk_bs22']\
                      + b2 * self.pt.pktable['pk_b2t'] + b3nl * self.pt.pktable['pk_sig3sq']
        self.power += b1**2 * (self.pt.pktable['A'][0] + self.pt.pktable['B'][0])
        self.power += b1 * (self.pt.pktable['A'][1] + self.pt.pktable['B'][1])
        self.power += (self.pt.pktable['A'][2] + self.pt.pktable['B'][2])


class TNSTracerCorrelationFunctionMultipoles(BaseTracerCorrelationFunctionFromPowerSpectrumMultipoles):
    r"""
    TNS tracer correlation function multipoles.

    Parameters
    ----------
    s : array, default=None
        Theory separations where to evaluate multipoles.

    ells : tuple, default=(0, 2, 4)
        Multipoles to compute.

    template : BasePowerSpectrumTemplate
        Power spectrum template. Defaults to :class:`DirectPowerSpectrumTemplate`.

    **kwargs : dict
        Options, defaults to: ``mu=8``.
    """


class EFTLikeTNSTracerPowerSpectrumMultipoles(BaseEFTLikeTracerPowerSpectrumMultipoles, TNSTracerPowerSpectrumMultipoles):
    r"""
    TNS tracer power spectrum multipoles with EFT-like counter and stochastic terms.
    Can be exactly marginalized over counter terms and stochastic terms ct*, sn*.

    Parameters
    ----------
    k : array, default=None
        Theory wavenumbers where to evaluate multipoles.

    ells : tuple, default=(0, 2, 4)
        Multipoles to compute.

    mu : int, default=8
        Number of :math:`\mu`-bins to use (in :math:`[0, 1]`).

    template : BasePowerSpectrumTemplate
        Power spectrum template. Defaults to :class:`DirectPowerSpectrumTemplate`.
    """


class EFTLikeTNSTracerCorrelationFunctionMultipoles(BaseTracerCorrelationFunctionFromPowerSpectrumMultipoles):
    r"""
    TNS tracer correlation function multipoles with EFT-like counter and stochastic terms.
    Can be exactly marginalized over counter terms and stochastic terms ct*, sn*.

    Parameters
    ----------
    s : array, default=None
        Theory separations where to evaluate multipoles.

    ells : tuple, default=(0, 2, 4)
        Multipoles to compute.

    template : BasePowerSpectrumTemplate
        Power spectrum template. Defaults to :class:`DirectPowerSpectrumTemplate`.

    **kwargs : dict
        Options, defaults to: ``mu=8``.
    """


class BaseVelocileptorsPowerSpectrumMultipoles(BasePTPowerSpectrumMultipoles, BaseTheoryPowerSpectrumMultipolesFromWedges):

    """Base class for velocileptor-based matter power spectrum multipoles."""
    _default_options = dict()

    def initialize(self, *args, **kwargs):
        super(BaseVelocileptorsPowerSpectrumMultipoles, self).initialize(*args, **kwargs)
        self.options['threads'] = self.options.pop('nthreads', 1)

    @classmethod
    def install(cls, installer):
        installer.pip('git+https://github.com/sfschen/velocileptors')

    def __getstate__(self):
        state = {}
        for name in self._pt_attrs:
            if hasattr(self.pt, name):
                state[name] = getattr(self.pt, name)
        for name in ['wmu']:
            state[name] = getattr(self, name)
        return state


class BaseVelocileptorsTracerPowerSpectrumMultipoles(BaseTracerPowerSpectrumMultipoles):

    """Base class for velocileptor-based tracer power spectrum multipoles."""
    _default_options = dict()

    def calculate(self, **params):
        pars = [params.get(name, value) for name, value in self.required_bias_params.items()]
        opts = {name: params.get(name, default) for name, default in self.optional_bias_params.items()}
        self.power = self.pt.combine_bias_terms_poles(pars, **opts, **self.options)


class BaseVelocileptorsCorrelationFunctionMultipoles(BasePTCorrelationFunctionMultipoles):

    """Base class for velocileptor-based matter correlation function multipoles."""
    _default_options = dict()

    def initialize(self, *args, **kwargs):
        super(BaseVelocileptorsCorrelationFunctionMultipoles, self).initialize(*args, **kwargs)
        self.options['threads'] = self.options.pop('nthreads', 1)

    def combine_bias_terms_poles(self, pars, **opts):
        return np.array([self.pt.compute_xi_ell(ss, self.template.f, *pars, apar=self.template.qpar, aperp=self.template.qper, **self.options, **opts) for ss in self.s]).T


class BaseVelocileptorsTracerCorrelationFunctionMultipoles(BaseTracerCorrelationFunctionMultipoles):

    """Base class for velocileptor-based tracer correlation function multipoles."""
    _default_options = dict()

    def calculate(self, **params):
        pars = [params.get(name, value) for name, value in self.required_bias_params.items()]
        opts = {name: params.get(name, default) for name, default in self.optional_bias_params.items()}
        self.corr = self.pt.combine_bias_terms_poles(pars, **opts, **self.options)


class LPTVelocileptorsPowerSpectrumMultipoles(BaseVelocileptorsPowerSpectrumMultipoles):

    _default_options = dict(kIR=0.2, cutoff=10, extrap_min=-5, extrap_max=3, N=4000, nthreads=1, jn=5)
    # Slow, ~ 4 sec per iteration

    def initialize(self, *args, mu=8, **kwargs):
        super(LPTVelocileptorsPowerSpectrumMultipoles, self).initialize(*args, mu=mu, method='leggauss', **kwargs)

    def calculate(self):

        def interp1d(x, y):
            return interpolate.interp1d(x, y, kind='cubic')

        from velocileptors.LPT import lpt_rsd_fftw
        lpt_rsd_fftw.interp1d = interp1d

        from velocileptors.LPT.lpt_rsd_fftw import LPT_RSD
        self.pt = LPT_RSD(self.template.k, self.template.pk_dd, **self.options)
        # print(self.template.f, self.k.shape, self.template.qpar, self.template.qper, self.template.k.shape, self.template.pk_dd.shape)
        self.pt.make_pltable(self.template.f, kv=self.k, apar=self.template.qpar, aperp=self.template.qper, ngauss=len(self.mu) // 2)
        pktable = {0: self.pt.p0ktable, 2: self.pt.p2ktable, 4: self.pt.p4ktable}
        self.pktable = np.array([pktable[ell] for ell in self.ells])

    def combine_bias_terms_poles(self, pars):
        # bias = [b1, b2, bs, b3, alpha0, alpha2, alpha4, alpha6, sn0, sn2, sn4]
        # pkells = self.pt.combine_bias_terms_pkell(bias)[1:]
        # return np.array([pkells[[0, 2, 4].index(ell)] for ell in self.ells])
        b1, b2, bs, b3, alpha0, alpha2, alpha4, alpha6, sn0, sn2, sn4 = pars
        bias_monomials = jnp.array([1, b1, b1**2, b2, b1 * b2, b2**2, bs, b1 * bs, b2 * bs, bs**2, b3, b1 * b3, alpha0, alpha2, alpha4, alpha6, sn0, sn2, sn4])
        return jnp.sum(self.pktable * bias_monomials, axis=-1)

    def __getstate__(self):
        state = {}
        for name in ['k', 'z', 'ells', 'pktable']:
            if hasattr(self, name):
                state[name] = getattr(self, name)
        return state

    @classmethod
    def install(cls, installer):
        installer.pip('git+https://github.com/sfschen/velocileptors')


class LPTVelocileptorsTracerPowerSpectrumMultipoles(BaseVelocileptorsTracerPowerSpectrumMultipoles):
    """
    Velocileptors Lagrangian perturbation theory (LPT) tracer power spectrum multipoles.
    Can be exactly marginalized over counter terms and stochastic parameters alpha*, sn*.

    Parameters
    ----------
    k : array, default=None
        Theory wavenumbers where to evaluate multipoles.

    ells : tuple, default=(0, 2, 4)
        Multipoles to compute.

    template : BasePowerSpectrumTemplate
        Power spectrum template. Defaults to :class:`DirectPowerSpectrumTemplate`.

    **kwargs : dict
        Velocileptors options, defaults to: ``kIR=0.2, cutoff=10, extrap_min=-5, extrap_max=3, N=4000, nthreads=1, jn=5, mu=8``.


    Reference
    ---------
    - https://arxiv.org/abs/2005.00523
    - https://arxiv.org/abs/2012.04636
    - https://github.com/sfschen/velocileptors
    """
    def set_params(self):
        self.required_bias_params = dict(b1=0.69, b2=-1.17, bs=-0.71, b3=0., alpha0=0., alpha2=0., alpha4=0., alpha6=0., sn0=0., sn2=0., sn4=0.)
        super(LPTVelocileptorsTracerPowerSpectrumMultipoles, self).set_params()
        fix = []
        if 4 not in self.ells: fix += ['alpha4', 'alpha6', 'sn4']
        if 2 not in self.ells: fix += ['alpha2', 'sn2']
        for name in fix: self.params[name].update(fixed=True)

    def calculate(self, **params):
        return super(LPTVelocileptorsTracerPowerSpectrumMultipoles, self).calculate(**params)


class LPTVelocileptorsTracerCorrelationFunctionMultipoles(BaseTracerCorrelationFunctionFromPowerSpectrumMultipoles):
    """
    Velocileptors LPT tracer correlation function multipoles.
    Can be exactly marginalized over counter terms and stochastic parameters alpha*, sn*.

    Parameters
    ----------
    s : array, default=None
        Theory separations where to evaluate multipoles.

    ells : tuple, default=(0, 2, 4)
        Multipoles to compute.

    template : BasePowerSpectrumTemplate
        Power spectrum template. Defaults to :class:`DirectPowerSpectrumTemplate`.

    **kwargs : dict
        Velocileptors options, defaults to: ``kIR=0.2, cutoff=10, extrap_min=-5, extrap_max=3, N=4000, nthreads=1, jn=5, mu=8``.


    Reference
    ---------
    - https://arxiv.org/abs/2005.00523
    - https://arxiv.org/abs/2012.04636
    - https://github.com/sfschen/velocileptors
    """


class EPTMomentsVelocileptorsPowerSpectrumMultipoles(BaseVelocileptorsPowerSpectrumMultipoles):

    # Original implementation does AP transform when combining with f and bias parameters
    # Here we make the AP transform, then update bias parameters, which allows analytic marginalization

    _default_options = dict(rbao=110, beyond_gauss=True,
                            one_loop=True, shear=True, third_order=True, cutoff=20, jn=5, N=4000,
                            nthreads=1, extrap_min=-5, extrap_max=3, import_wisdom=False)
    _pt_attrs = ['pktable', 'vktable', 's0ktable', 's2ktable', 'g1ktable', 'g3ktable', 'k0', 'k2', 'k4', 'plin_ir', 'kap', 'muap', 'f']

    def initialize(self, *args, mu=4, method='leggauss', **kwargs):
        super(EPTMomentsVelocileptorsPowerSpectrumMultipoles, self).initialize(*args, mu=mu, method=method, **kwargs)
        self.template.init.update(with_now='peakaverage')

    def calculate(self):
        from velocileptors.EPT.moment_expansion_fftw import MomentExpansion
        # default is kmin=1e-2, kmax=0.5, nk=100
        self.pt = MomentExpansion(self.template.k, self.template.pk_dd, pnw=self.template.pknow_dd, kmin=self.k[0], kmax=self.k[-1], nk=len(self.k), **self.options)
        jac, self.kap, self.muap = self.template.ap_k_mu(self.k, self.mu)
        self.f = self.template.f
        for name in self._pt_attrs:
            if name in ['kap', 'muap', 'f']:
                setattr(self.pt, name, getattr(self, name))
            else:
                value = getattr(self.pt, name)
                tmp = np.swapaxes(jac * interpolate.interp1d(self.pt.kv, value, kind='cubic', fill_value='extrapolate', axis=0)(self.kap), 1, -1)
                setattr(self.pt, name, tmp)

    def __setstate__(self, state):
        from velocileptors.EPT.moment_expansion_fftw import MomentExpansion
        self.pt = MomentExpansion.__new__(MomentExpansion)
        self.pt.__dict__.update(state)

    def combine_bias_terms_poles(self, pars, counterterm_c3=0, beyond_gauss=False, reduced=True):
        if beyond_gauss:
            if reduced:
                b1, b2, bs, b3, alpha0, alpha2, alpha4, alpha6, sn, sn2, sn4 = pars
                alpha, alphav, alpha_s0, alpha_s2, alpha_g1, alpha_g3, alpha_k2 = alpha0, alpha2, 0, alpha4, 0, 0, alpha6
                sn, sv, sigma0, stoch_k0 = sn, sn2, 0, sn4
            else:
                b1, b2, bs, b3, alpha, alphav, alpha_s0, alpha_s2, alpha_g1, alpha_g3, alpha_k2, sn, sv, sigma0, stoch_k0 = pars
        else:
            if reduced:
                b1, b2, bs, b3, alpha0, alpha2, alpha4, sn, sn2 = pars
                alpha, alphav, alpha_s0, alpha_s2 = alpha0, alpha2, 0, alpha4
                sn, sv, sigma0 = sn, sn2, 0
            else:
                b1, b2, bs, b3, alpha, alphav, alpha_s0, alpha_s2, sn, sv, sigma0 = pars

        pt = self.pt
        kap, muap, f = pt.kap, pt.muap, pt.f
        muap2 = muap**2

        pk = pt.combine_bias_terms_pk(b1, b2, bs, b3, alpha, sn)
        vk = pt.combine_bias_terms_vk(b1, b2, bs, b3, alphav, sv)
        s0k, s2k = pt.combine_bias_terms_sk(b1, b2, bs, b3, alpha_s0, alpha_s2, sigma0)

        pkmu = pk - f * kap * muap2 * vk - 0.5 * f**2 * kap**2 * muap2 * (s0k + 0.5 * s2k * (3 * muap2 - 1))

        if beyond_gauss:
            g1k, g3k = pt.combine_bias_terms_gk(b1, b2, bs, b3, alpha_g1, alpha_g3)
            k0k, k2k, k4k = pt.combine_bias_terms_kk(b1, b2, bs, b3, alpha_k2, stoch_k0)
            pkmu += 1. / 6. * self.f**3 * (kap * muap)**3 * (g1k * muap + g3k * muap**3)\
                    + 1. / 24. * self.f**4 * (kap * muap)**4 * (k0k + k2k * muap2 + k4k * muap2**2)
        else:
            pkmu += 1. / 6. * counterterm_c3 * kap**2 * muap2**2 * pt.plin_ir

        # Interpolate onto true wavenumbers
        return self.to_poles(pkmu)


class EPTMomentsVelocileptorsTracerPowerSpectrumMultipoles(BaseVelocileptorsTracerPowerSpectrumMultipoles):
    """
    Velocileptors Eulerian perturbation theory (EPT) tracer power spectrum multipoles with moment expansion.

    Parameters
    ----------
    k : array, default=None
        Theory wavenumbers where to evaluate multipoles.

    ells : tuple, default=(0, 2, 4)
        Multipoles to compute.

    template : BasePowerSpectrumTemplate
        Power spectrum template. Defaults to :class:`DirectPowerSpectrumTemplate`.

    **kwargs : dict
        Velocileptors options, defaults to: ``rbao=110, kmin=1e-2, kmax=0.5, nk=100, beyond_gauss=True,
        one_loop=True, shear=True, third_order=True, cutoff=20, jn=5, N=4000, nthreads=1, extrap_min=-5, extrap_max=3, import_wisdom=False, reduce=True, mu=4``.


    Reference
    ---------
    - https://arxiv.org/abs/2005.00523
    - https://arxiv.org/abs/2012.04636
    - https://github.com/sfschen/velocileptors
    """
    _default_options = dict(beyond_gauss=True, reduced=True)

    def set_params(self):
        if self.options['beyond_gauss']:
            if self.options['reduced']:
                self.required_bias_params = ['b1', 'b2', 'bs', 'b3', 'alpha0', 'alpha2', 'alpha4', 'alpha6', 'sn0', 'sn2', 'sn4']
            else:
                self.required_bias_params = ['b1', 'b2', 'bs', 'b3', 'alpha', 'alpha_v', 'alpha_s0', 'alpha_s2', 'alpha_g1',\
                                             'alpha_g3', 'alpha_k2', 'sn0', 'sv', 'sigma0', 'stoch_k0']
        else:
            if self.options['reduced']:
                self.required_bias_params = ['b1', 'b2', 'bs', 'b3', 'alpha0', 'alpha2', 'alpha4', 'sn0', 'sn2']
            else:
                self.required_bias_params = ['b1', 'b2', 'bs', 'b3', 'alpha', 'alpha_v', 'alpha_s0', 'alpha_s2', 'sn0', 'sv', 'sigma0']

        default_values = {'b1': 1.69, 'b2': -1.17, 'bs': -0.71, 'b3': -0.479, 'counterterm_c3': 0.}
        self.required_bias_params = {name: default_values.get(name, 0.) for name in self.required_bias_params}
        self.optional_bias_params = {name: default_values.get(name, 0.) for name in self.optional_bias_params}
        self.params = self.params.select(basename=list(self.required_bias_params.keys()) + list(self.optional_bias_params.keys()))


class EPTMomentsVelocileptorsTracerCorrelationFunctionMultipoles(BaseTracerCorrelationFunctionFromPowerSpectrumMultipoles):
    """
    Velocileptors EPT moments tracer correlation function multipoles.
    Can be exactly marginalized over counter terms and stochastic parameters alpha*, sn*.

    Parameters
    ----------
    s : array, default=None
        Theory separations where to evaluate multipoles.

    ells : tuple, default=(0, 2, 4)
        Multipoles to compute.

    template : BasePowerSpectrumTemplate
        Power spectrum template. Defaults to :class:`DirectPowerSpectrumTemplate`.

    **kwargs : dict
        Velocileptors options, defaults to: ``rbao=110, kmin=1e-2, kmax=0.5, nk=100, beyond_gauss=True,
        one_loop=True, shear=True, third_order=True, cutoff=20, jn=5, N=4000, nthreads=1, extrap_min=-5, extrap_max=3, import_wisdom=False, reduce=True, mu=8``.


    Reference
    ---------
    , rather use dynamic nested sampling- https://arxiv.org/abs/2005.00523
    - https://arxiv.org/abs/2012.04636
    - https://github.com/sfschen/velocileptors
    """


class LPTMomentsVelocileptorsPowerSpectrumMultipoles(BaseVelocileptorsPowerSpectrumMultipoles):

    _default_options = dict(beyond_gauss=False, one_loop=True,
                            shear=True, third_order=True, cutoff=10, jn=5, N=2000, nthreads=1,
                            extrap_min=-5, extrap_max=3, import_wisdom=False)
    _pt_attrs = ['pktable', 'vktable', 'stracektable', 'sparktable', 'gamma1ktable', 'kappaktable', 'kap', 'muap', 'f', 'third_order']

    def initialize(self, *args, mu=8, method='leggauss', **kwargs):
        super(LPTMomentsVelocileptorsPowerSpectrumMultipoles, self).initialize(*args, mu=mu, method=method, **kwargs)

    def calculate(self):
        from velocileptors.LPT.moment_expansion_fftw import MomentExpansion
        # default is kmin=5e-3, kmax=0.3, nk=50
        self.pt = MomentExpansion(self.template.k, self.template.pk_dd, kmin=self.k[0], kmax=self.k[-1], nk=len(self.k), **self.options)
        jac, self.kap, self.muap = self.template.ap_k_mu(self.k, self.mu)
        self.f = self.template.f
        for name in self._pt_attrs:
            if name in ['kap', 'muap', 'f']:
                setattr(self.pt, name, getattr(self, name))
            elif name not in ['third_order'] and hasattr(self.pt, name):
                value = getattr(self.pt, name)
                tmp = jac * interpolate.interp1d(self.pt.kv, value, kind='cubic', fill_value='extrapolate', axis=0)(self.kap.ravel())
                setattr(self.pt, name, tmp)

    def __setstate__(self, state):
        from velocileptors.LPT.moment_expansion_fftw import MomentExpansion
        self.pt = MomentExpansion.__new__(MomentExpansion)
        self.pt.__dict__.update(state)
        # This is very unfortunate, but otherwise jax arrays (generated by emulators) will fail when doing combine_bias_terms_sk, combine_bias_terms_gk,
        # because of item assignments.
        # It would be *really* nice that velocileptors is more jax-compatible...
        for name in ['stracektable', 'sparktable', 'gamma1ktable']:
            if name in state:
                setattr(self.pt, name, np.asarray(state[name]))

    def combine_bias_terms_poles(self, pars, counterterm_c3=0, beyond_gauss=False, reduced=True):
        pt = self.pt
        kap, muap, f, pktable = pt.kap, pt.muap, pt.f, pt.pktable
        shape = kap.shape
        kap, muap = (x.ravel() for x in np.broadcast_arrays(kap, muap))
        muap2 = muap**2
        from velocileptors.LPT import cleft_fftw, velocity_moments_fftw
        cleft_fftw.np = velocity_moments_fftw.np = jnp

        if beyond_gauss:
            if reduced:
                b1, b2, bs, b3, alpha0, alpha2, alpha4, alpha6, sn, sn2, sn4 = pars

                kv, pk = pt.combine_bias_terms_pk(b1, b2, bs, b3, alpha0, sn)
                kv, vk = pt.combine_bias_terms_vk(b1, b2, bs, b3, alpha2, sn2)
                kv, s0, s2 = pt.combine_bias_terms_sk(b1, b2, bs, b3, 0, alpha4, 0, basis='Polynomial')
                kv, g1, g3 = pt.combine_bias_terms_gk(b1, b2, bs, b3, 0, alpha6)
                kv, k0, k2, k4 = pt.combine_bias_terms_kk(0, sn4)

            else:
                b1, b2, bs, b3, alpha, alpha_v, alpha_s0, alpha_s2, alpha_g1, alpha_g3, alpha_k2, sn, sv, sigma0_stoch, sn4 = pars

                kv, pk = pt.combine_bias_terms_pk(b1, b2, bs, b3, alpha, sn)
                kv, vk = pt.combine_bias_terms_vk(b1, b2, bs, b3, alpha_v, sv)
                kv, s0, s2 = pt.combine_bias_terms_sk(b1, b2, bs, b3, alpha_s0, alpha_s2, sigma0_stoch, basis='Polynomial')
                kv, g1, g3 = pt.combine_bias_terms_gk(b1, b2, bs, b3, alpha_g1, alpha_g3)
                kv, k0, k2, k4 = pt.combine_bias_terms_kk(alpha_k2, sn4)

            pkmu = pk - f * kap * muap2 * vk -\
                   1. / 2 * f**2 * kap**2 * muap2 * (s0 + s2 * muap2) +\
                   1. / 6 * f**3 * kap**3 * muap**3 * (g1 + muap2 * g3) +\
                   1. / 24 * f**4 * kv**4 * muap**4 * (k0 + muap2 * k2 + muap2**2 * k4)

        else:
            if reduced:
                b1, b2, bs, b3, alpha0, alpha2, alpha4, sn, sn2 = pars
                ct3 = alpha4

                kv, pk = pt.combine_bias_terms_pk(b1, b2, bs, b3, alpha0, sn)
                kv, vk = pt.combine_bias_terms_vk(b1, b2, bs, b3, alpha2, sn2)
                kv, s0, s2 = pt.combine_bias_terms_sk(b1, b2, bs, b3, 0, 0, 0, basis='Polynomial')

            else:
                b1, b2, bs, b3, alpha, alpha_v, alpha_s0, alpha_s2, sn, sv, sigma0_stoch = pars
                ct3 = counterterm_c3

                kv, pk = pt.combine_bias_terms_pk(b1, b2, bs, b3, alpha, sn)
                kv, vk = pt.combine_bias_terms_vk(b1, b2, bs, b3, alpha_v, sv)
                kv, s0, s2 = pt.combine_bias_terms_sk(b1, b2, bs, b3, alpha_s0, alpha_s2, sigma0_stoch, basis='Polynomial')

            pkmu = pk - f * kap * muap2 * vk -\
                   0.5 * f**2 * kap**2 * muap2 * (s0 + s2 * muap2) +\
                   ct3 / 6. * kap**2 * muap2**2 * pktable[:, -1]

        cleft_fftw.np = velocity_moments_fftw.np = np
        return self.to_poles(pkmu.reshape(shape))


class LPTMomentsVelocileptorsTracerPowerSpectrumMultipoles(BaseVelocileptorsTracerPowerSpectrumMultipoles):
    """
    Velocileptors Lagrangian perturbation theory (LPT) tracer power spectrum multipoles with moment expansion.

    Parameters
    ----------
    k : array, default=None
        Theory wavenumbers where to evaluate multipoles.

    ells : tuple, default=(0, 2, 4)
        Multipoles to compute.

    template : BasePowerSpectrumTemplate
        Power spectrum template. Defaults to :class:`DirectPowerSpectrumTemplate`.

    **kwargs : dict
        Velocileptors options, defaults to: ``kmin=5e-3, kmax=0.3, nk=50, beyond_gauss=False, one_loop=True,
        shear=True, third_order=True, cutoff=10, jn=5, N=2000, nthreads=1, extrap_min=-5, extrap_max=3, import_wisdom=False, mu=8``.


    Reference
    ---------
    , rather use dynamic nested sampling- https://arxiv.org/abs/2005.00523
    - https://arxiv.org/abs/2012.04636
    - https://github.com/sfschen/velocileptors
    """
    _default_options = dict(beyond_gauss=False, shear=True, third_order=True, reduced=True)

    def set_params(self):
        if self.options['beyond_gauss']:
            if self.options['reduced']:
                self.required_bias_params = ['b1', 'b2', 'bs', 'b3', 'alpha0', 'alpha2', 'alpha4', 'alpha6', 'sn0', 'sn2', 'sn4']
            else:
                self.required_bias_params = ['b1', 'b2', 'bs', 'b3', 'alpha', 'alpha_v', 'alpha_s0', 'alpha_s2', 'alpha_g1',\
                                             'alpha_g3', 'alpha_k2', 'sn0', 'sv', 'sigma0_stoch', 'sn4']
        else:
            if self.options['reduced']:
                self.required_bias_params = ['b1', 'b2', 'bs', 'b3', 'alpha0', 'alpha2', 'alpha4', 'sn0', 'sn2']
            else:
                self.required_bias_params = ['b1', 'b2', 'bs', 'b3', 'alpha', 'alpha_v', 'alpha_s0', 'alpha_s2',
                                             'sn0', 'sv', 'sigma0_stoch']

        self.optional_bias_params = ['counterterm_c3']
        default_values = {'b1': 1.69, 'b2': -1.17, 'bs': -0.71, 'b3': -0.479}
        self.required_bias_params = {name: default_values.get(name, 0.) for name in self.required_bias_params}
        self.optional_bias_params = {name: default_values.get(name, 0.) for name in self.optional_bias_params}
        if not self.options['shear']:
            self.required_bias_params.pop('bs')
        if not self.options['third_order']:
            self.required_bias_params.pop('b3')
        del self.options['shear'], self.options['third_order']
        self.params = self.params.select(basename=list(self.required_bias_params.keys()) + list(self.optional_bias_params.keys()))


class LPTMomentsVelocileptorsTracerCorrelationFunctionMultipoles(BaseTracerCorrelationFunctionFromPowerSpectrumMultipoles):
    """
    Velocileptors LPT moments tracer correlation function multipoles.
    Can be exactly marginalized over counter terms and stochastic parameters alpha*, sn*.

    Parameters
    ----------
    s : array, default=None
        Theory separations where to evaluate multipoles.

    ells : tuple, default=(0, 2, 4)
        Multipoles to compute.

    template : BasePowerSpectrumTemplate
        Power spectrum template. Defaults to :class:`DirectPowerSpectrumTemplate`.

    **kwargs : dict
        Velocileptors options, defaults to: ``kmin=5e-3, kmax=0.3, nk=50, beyond_gauss=False, one_loop=True,
        shear=True, third_order=True, cutoff=10, jn=5, N=2000, nthreads=1, extrap_min=-5, extrap_max=3, import_wisdom=False``.


    Reference
    ---------
    - https://arxiv.org/abs/2005.00523
    - https://arxiv.org/abs/2012.04636
    - https://github.com/sfschen/velocileptors
    """


class PyBirdPowerSpectrumMultipoles(BasePTPowerSpectrumMultipoles):

    _default_options = dict(optiresum=True, nd=None, with_nnlo_higher_derivative=False, with_nnlo_counterterm=False, with_stoch=False, with_resum='opti')
    _pt_attrs = ['co', 'f', 'eft_basis', 'with_stoch', 'with_nnlo_counterterm', 'with_tidal_alignments',
                 'P11l', 'Ploopl', 'Pctl', 'Pstl', 'Pnnlol', 'C11l', 'Cloopl', 'Cctl', 'Cstl', 'Cnnlol', 'bst']

    def initialize(self, *args, shotnoise=1e4, **kwargs):
        import pybird_dev as pybird
        super(PyBirdPowerSpectrumMultipoles, self).initialize(*args, **kwargs)
        if self.options['nd'] is None: self.options['nd'] = 1. / shotnoise
        # print(self.k[0] * 0.8, self.k[-1] * 1.2)
        self.co = pybird.Common(halohalo=True, with_time=True, exact_time=False, quintessence=False, with_tidal_alignments=False, nonequaltime=False,
                                Nl=len(self.ells), kmin=self.k[0] * 0.8, kmax=self.k[-1] * 1.2, optiresum=self.options['with_resum'] == 'opti',
                                nd=self.options['nd'], with_cf=False)
        self.nonlinear = pybird.NonLinear(load=False, save=False, co=self.co)
        self.resum = pybird.Resum(co=self.co)
        self.nnlo_higher_derivative = self.nnlo_counterterm = None
        if self.options['with_nnlo_higher_derivative']:
            self.nnlo_higher_derivative = pybird.NNLO_higher_derivative(self.co.k, with_cf=False, co=self.co)
        if self.options['with_nnlo_counterterm']:
            self.nnlo_counterterm = pybird.NNLO_counterterm(co=self.co)
        self.projection = pybird.Projection(self.k, Om_AP=0.3, z_AP=1., co=self.co)  # placeholders for Om_AP and z_AP, as we will provide q's

    def calculate(self):
        import pybird_dev as pybird
        cosmo = {'k11': self.template.k, 'P11': self.template.pk_dd, 'f': self.template.f, 'DA': 1., 'H': 1.}
        self.pt = pybird.Bird(cosmo, with_bias=False, eft_basis='eftoflss', with_stoch=self.options['with_stoch'], with_nnlo_counterterm=self.nnlo_counterterm is not None, co=self.co)

        if self.nnlo_counterterm is not None:  # we use smooth power spectrum since we don't want spurious BAO signals
            self.nnlo_counterterm.Ps(self.pt, np.log(self.template.pknow_dd))

        self.nonlinear.PsCf(self.pt)
        self.pt.setPsCfl()

        if self.options['with_resum']:
            self.resum.Ps(self.pt)

        self.projection.AP(self.pt, q=(self.template.qper, self.template.qpar))
        self.projection.xdata(self.pt)

    def combine_bias_terms_poles(self, **params):
        from pybird_dev import bird
        bird.np = jnp
        self.pt.setreducePslb(params, what='full')
        bird.np = np
        return self.pt.fullPs

    def __getstate__(self):
        state = {}
        for name in self._pt_attrs:
            if hasattr(self.pt, name):
                state[name] = getattr(self.pt, name)
        return state

    def __setstate__(self, state):
        import pybird_dev as pybird
        self.pt = pybird.Bird.__new__(pybird.Bird)
        self.pt.with_bias = False
        self.pt.__dict__.update(state)

    @classmethod
    def install(cls, installer):
        installer.pip('git+https://github.com/adematti/pybird@dev')


class PyBirdTracerPowerSpectrumMultipoles(BaseTracerPowerSpectrumMultipoles):
    """
    Pybird tracer power spectrum multipoles.
    Can be exactly marginalized over counterterms c*.

    Parameters
    ----------
    k : array, default=None
        Theory wavenumbers where to evaluate multipoles.

    ells : tuple, default=(0, 2, 4)
        Multipoles to compute.

    template : BasePowerSpectrumTemplate
        Power spectrum template. Defaults to :class:`DirectPowerSpectrumTemplate`.

    shotnoise : float, default=1e4
        Shot noise (which is usually marginalized over).

    **kwargs : dict
        Pybird options, defaults to: ``optiresum=True, nd=None, with_nnlo_higher_derivative=False, with_nnlo_counterterm=False, with_stoch=False, with_resum='opti', eft_basis='eftoflss'``.


    Reference
    ---------
    - https://arxiv.org/abs/2003.07956
    - https://github.com/pierrexyz/pybird
    """
    _default_options = dict(with_nnlo_higher_derivative=False, with_nnlo_counterterm=False, with_stoch=True, eft_basis='eftoflss')

    def set_params(self):
        self.required_bias_params = ['b1', 'b3', 'cct']
        allowed_eft_basis = ['eftoflss', 'westcoast']
        if self.options['eft_basis'] not in allowed_eft_basis:
            raise ValueError('eft_basis must be one of {}'.format(allowed_eft_basis))
        if self.options['eft_basis'] == 'westcoast':
            self.required_bias_params += ['b2p4', 'b2m4']
        else:
            self.required_bias_params += ['b2', 'b4']
        if len(self.ells) >= 2: self.required_bias_params += ['cr1', 'cr2']
        if self.options['with_stoch']:
            self.required_bias_params += ['ce0', 'ce1', 'ce2']
        if self.options['with_nnlo_counterterm']:
            self.required_bias_params += ['cr4', 'cr6']
        default_values = {'b1': 1.69, 'b3': -0.479}
        self.required_bias_params = {name: default_values.get(name, 0.) for name in self.required_bias_params}
        self.params = self.params.select(basename=list(self.required_bias_params.keys()) + list(self.optional_bias_params.keys()))

    def transform_params(self, **params):
        if self.options['eft_basis'] == 'westcoast':
            params['b2'] = (params['b2p4'] + params['b2m4']) / 2.**0.5
            params['b4'] = (params.pop('b2p4') - params.pop('b2m4')) / 2.**0.5
        return params

    def calculate(self, **params):
        self.power = self.pt.combine_bias_terms_poles(**self.transform_params(**params))


class PyBirdCorrelationFunctionMultipoles(BasePTCorrelationFunctionMultipoles):

    _default_options = dict(optiresum=True, nd=None, with_nnlo_higher_derivative=False, with_nnlo_counterterm=False, with_stoch=False, with_resum='opti')
    _pt_attrs = ['co', 'f', 'eft_basis', 'with_stoch', 'with_nnlo_counterterm', 'with_tidal_alignments',
                 'P11l', 'Ploopl', 'Pctl', 'Pstl', 'Pnnlol', 'C11l', 'Cloopl', 'Cctl', 'Cstl', 'Cnnlol']

    def initialize(self, *args, shotnoise=1e4, **kwargs):
        import pybird_dev as pybird
        super(PyBirdCorrelationFunctionMultipoles, self).initialize(*args, **kwargs)
        if self.options['nd'] is None: self.options['nd'] = 1. / shotnoise
        self.co = pybird.Common(halohalo=True, with_time=True, exact_time=False, quintessence=False, with_tidal_alignments=False, nonequaltime=False,
                                Nl=len(self.ells), kmin=1e-3, kmax=0.25, optiresum=self.options['with_resum'] == 'opti',
                                nd=self.options['nd'], with_cf=True, accboost=1.)
        self.nonlinear = pybird.NonLinear(load=False, save=False, co=self.co)  # NFFT=256, fftbias=-1.6
        self.resum = pybird.Resum(co=self.co)  # LambdaIR=.2, NFFT=192
        self.nnlo_higher_derivative = self.nnlo_counterterm = None
        if self.options['with_nnlo_higher_derivative']:
            self.nnlo_higher_derivative = pybird.NNLO_higher_derivative(self.co.k, with_cf=True, co=self.co)
        if self.options['with_nnlo_counterterm']:
            self.nnlo_counterterm = pybird.NNLO_counterterm(co=self.co)
        self.projection = pybird.Projection(self.s, Om_AP=0.3, z_AP=1., co=self.co)  # placeholders for Om_AP and z_AP, as we will provide q's

    def calculate(self):
        import pybird_dev as pybird
        cosmo = {'k11': self.template.k, 'P11': self.template.pk_dd, 'f': self.template.f, 'DA': 1., 'H': 1.}
        self.pt = pybird.Bird(cosmo, with_bias=False, eft_basis='eftoflss', with_stoch=self.options['with_stoch'], with_nnlo_counterterm=self.nnlo_counterterm is not None, co=self.co)

        if self.nnlo_counterterm is not None:  # we use smooth power spectrum since we don't want spurious BAO signals
            assert np.allclose(self.template.k, self.pt.kin)
            self.nnlo_counterterm.Cf(self.pt, np.log(self.template.pknow_dd))

        self.nonlinear.PsCf(self.pt)
        self.pt.setPsCfl()

        if self.options['with_resum']:
            self.resum.PsCf(self.pt)

        self.projection.AP(self.pt, q=(self.template.qper, self.template.qpar))
        self.projection.xdata(self.pt)

    def combine_bias_terms_poles(self, **params):
        from pybird_dev import bird
        bird.np = jnp
        self.pt.setreduceCflb(params)
        bird.np = np
        return self.pt.fullCf

    def __getstate__(self):
        state = {}
        for name in self._pt_attrs:
            if hasattr(self.pt, name):
                state[name] = getattr(self.pt, name)
        return state

    def __setstate__(self, state):
        import pybird_dev as pybird
        self.pt = pybird.Bird.__new__(pybird.Bird)
        self.pt.with_bias = False
        self.pt.__dict__.update(state)

    @classmethod
    def install(cls, installer):
        installer.pip('git+https://github.com/adematti/pybird@dev')


class PyBirdTracerCorrelationFunctionMultipoles(BaseTracerCorrelationFunctionMultipoles):
    """
    Pybird tracer correlation function multipoles.
    Can be exactly marginalized over counterterms c*.

    Parameters
    ----------
    s : array, default=None
        Theory separations where to evaluate multipoles.

    ells : tuple, default=(0, 2, 4)
        Multipoles to compute.

    template : BasePowerSpectrumTemplate
        Power spectrum template. Defaults to :class:`DirectPowerSpectrumTemplate`.

    shotnoise : float, default=1e4
        Shot noise (which is usually marginalized over).

    **kwargs : dict
        Pybird options, defaults to: ``optiresum=True, nd=None, with_nnlo_higher_derivative=False, with_nnlo_counterterm=False, with_stoch=False, with_resum='opti', eft_basis='eftoflss'``.
    """
    _default_options = dict(with_nnlo_higher_derivative=False, with_nnlo_counterterm=False, with_stoch=False, eft_basis='eftoflss')

    def set_params(self):
        return PyBirdTracerPowerSpectrumMultipoles.set_params(self)

    def transform_params(self, **params):
        return PyBirdTracerPowerSpectrumMultipoles.transform_params(self, **params)

    def calculate(self, **params):
        self.corr = self.pt.combine_bias_terms_poles(**self.transform_params(**params))
