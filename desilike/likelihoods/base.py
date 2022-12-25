import numpy as np

from desilike.base import BaseCalculator, Parameter, ParameterArray
from desilike.utils import jnp
from desilike import utils


class BaseLikelihood(BaseCalculator):

    _attrs = ['loglikelihood', 'logprior']

    def initialize(self):
        for name in self._attrs:
            if name not in self.params.basenames():
                self.params.set(Parameter(basename=name, namespace=self.runtime_info.namespace, latex=utils.outputs_to_latex(name), derived=True))
            param = self.params.select(basename=name)
            if not len(param):
                raise ValueError('{} derived parameter not found'.format(name))
            elif len(param) > 1:
                raise ValueError('Several parameters with name {:0} found. Which one is the {:0}?'.format(name))
            param = param[0]
            param.update(derived=True)
            setattr(self, '_param_{}'.format(name), param)

    def get(self):
        self.logprior = 0.
        pipeline = self.runtime_info.pipeline
        for param in pipeline.varied_params:
            self.logprior += param.prior(pipeline.param_values[param.name])
        return self.loglikelihood + self.logprior

    @classmethod
    def sum(cls, *others):
        if len(others) == 1 and utils.is_sequence(others[0]):
            others = others[0]
        likelihoods = []
        for likelihood in others: likelihoods += getattr(likelihood, 'likelihoods', [likelihood])
        return SumLikelihood(likelihoods=likelihoods)

    def __add__(self, other):
        return self.sum(self, other)

    def __radd__(self, other):
        if other == 0:
            return self.sum(self)
        return self.__add__(other)

    def __iadd__(self, other):
        if other == 0:
            return self.sum(self)
        return self.__add__(other)


class BaseGaussianLikelihood(BaseLikelihood):

    _attrs = ['loglikelihood', 'logprior']
    solved_default = '.marg'

    def initialize(self, flatdata, covariance=None, precision=None):
        self.flatdata = np.ravel(flatdata)
        if precision is None:
            if covariance is None:
                raise ValueError('Provide either precision or covariance matrix to {}'.format(self.__class__))
            self.precision = utils.inv(np.atleast_2d(np.array(covariance, dtype='f8')))
        else:
            self.precision = np.atleast_2d(np.array(precision, dtype='f8'))
        super(BaseGaussianLikelihood, self).initialize()

    def calculate(self):
        self.flatdiff = self.flattheory - self.flatdata
        self.loglikelihood = -0.5 * self.flatdiff.dot(self.precision).dot(self.flatdiff)

    def get(self):
        return self._solve()

    def _solve(self):
        # Analytic marginalization, to be called, if desired, in get()
        pipeline = self.runtime_info.pipeline
        all_params = self.all_params
        likelihoods = getattr(self, 'likelihoods', [self])

        solved_params, indices_best, indices_marg = [], [], []
        for param in all_params:
            solved = param.derived
            if param.solved:
                iparam = len(solved_params)
                solved_params.append(param)
                if solved == '.auto':
                    solved = self.solved_default
                if solved == '.best':
                    indices_best.append(iparam)
                elif solved == '.marg':  # marg
                    indices_marg.append(iparam)
                else:
                    raise ValueError('Unknown option for solved = {}'.format(solved))

        dx, x, solve_likelihoods = [], [], []

        if solved_params:

            solve_likelihoods = [likelihood for likelihood in likelihoods if any(param.solved for param in likelihood.all_params)]

            def getter():
                toret = []
                for likelihood in solve_likelihoods:
                    try:
                        toret.append(likelihood.flatdiff)
                        likelihood.precision
                    except AttributeError as exc:
                        raise AttributeError('{} must have both flatdiff and precision attributes to perform analytic marginalization'.format(likelihood))
                return toret  # jax understands lists

            flatdiffs = getter()
            # flatdiff is model - data
            jacs = pipeline.jac(getter, solved_params)
            projections, inverse_fishers = [], []

            for likelihood, flatdiff, jac in zip(solve_likelihoods, flatdiffs, jacs):
                zeros = np.zeros_like(likelihood.precision, shape=likelihood.precision.shape[0])
                jac = np.column_stack([jac[param.name] if param.name in jac else zeros for param in solved_params])
                projector = likelihood.precision.dot(jac)
                projection = projector.T.dot(flatdiff)
                invfisher = jac.T.dot(projector)
                projections.append(projection)
                inverse_fishers.append(invfisher)

            inverse_priors, x0 = [], []
            for param in solved_params:
                scale = getattr(param.prior, 'scale', None)
                inverse_priors.append(0. if scale is None or param.fixed else scale**(-2))
                x0.append(pipeline.param_values[param.name])

            inverse_priors = np.array(inverse_priors)
            sum_inverse_fishers = sum(inverse_fishers + [np.diag(inverse_priors)])
            dx = - np.linalg.solve(sum_inverse_fishers, sum(projections))
            x = x0 + dx

        sum_loglikelihood = 0.
        self.logprior = sum_logprior = 0.

        for param, xx in zip(solved_params, x):
            sum_logprior += all_params[param].prior(xx)
            pipeline.param_values[param.name] = xx
            pipeline.derived.set(ParameterArray(xx, param))

        for likelihood in likelihoods:
            # Modify derived loglikelihood in-place
            loglikelihood = float(likelihood.loglikelihood)
            if likelihood in solve_likelihoods:
                index = solve_likelihoods.index(likelihood)
                # Note: priors of solved params have already been added
                if indices_best:
                    loglikelihood -= 1. / 2. * dx[indices_best].dot(inverse_fishers[index][np.ix_(indices_best, indices_best)]).dot(dx[indices_best])
                    loglikelihood -= projections[index][indices_best].dot(dx[indices_best])
                if indices_marg:
                    loglikelihood += 1. / 2. * dx[indices_marg].dot(inverse_fishers[index][np.ix_(indices_marg, indices_marg)]).dot(dx[indices_marg])
            # Set derived values
            likelihood.runtime_info.derived.set(ParameterArray(loglikelihood, likelihood._param_loglikelihood))
            sum_loglikelihood += loglikelihood
        if indices_marg:
            sum_loglikelihood -= 1. / 2. * np.linalg.slogdet(sum_inverse_fishers[np.ix_(indices_marg, indices_marg)])[1]
            #sum_loglikelihood += 1. / 2. * len(indices_marg) * np.log(2. * np.pi)
            # Convention: in the limit of no likelihood constraint on dx, no change to the loglikelihood
            # This allows to ~ keep the interpretation in terms of -1./2. chi2
            ip = inverse_priors[indices_marg]
            sum_loglikelihood += 1. / 2. * np.sum(np.log(ip[ip > 0.]))  # logdet
            #sum_loglikelihood -= 1. / 2. * len(indices_marg) * np.log(2. * np.pi)

        self.loglikelihood = sum_loglikelihood
        self.logprior = sum_logprior

        for param in all_params:
            if param.varied and not param.solved:
                if param.derived:
                    array = pipeline.derived[param]
                    self.logprior += array.param.prior(array)
                else:
                    self.logprior += param.prior(pipeline.param_values[param.name])

        self.runtime_info.derived.set(ParameterArray(self.loglikelihood, self._param_loglikelihood))
        self.runtime_info.derived.set(ParameterArray(self.logprior, self._param_logprior))
        return self.loglikelihood + self.logprior

    def __getstate__(self):
        state = {}
        for name in ['flatdiff', 'flatdata', 'covariance', 'precision', 'loglikelihood']:
            if hasattr(self, name):
                state[name] = getattr(self, name)
        return state


class ObservablesGaussianLikelihood(BaseGaussianLikelihood):

    def initialize(self, observables, covariance=None, scale_covariance=1.):
        if not utils.is_sequence(observables):
            observables = [observables]
        self.nobs = None
        self.observables = [obs.runtime_info.initialize() for obs in observables]
        if covariance is None:
            nmocks = [self.mpicomm.bcast(len(obs.mocks) if self.mpicomm.rank == 0 and getattr(obs, 'mocks', None) is not None else 0) for obs in self.observables]
            if any(nmocks):
                self.nobs = nmocks[0]
                if not all(nmock == nmocks[0] for nmock in nmocks):
                    raise ValueError('Provide the same number of mocks for each observable, found {}'.format(nmocks))
                if self.mpicomm.rank == 0:
                    list_y = [np.concatenate(y, axis=0) for y in zip(*[obs.mocks for obs in self.observables])]
                    covariance = np.cov(list_y, rowvar=False, ddof=1)
                if isinstance(scale_covariance, bool):
                    if scale_covariance:
                        scale_covariance = 1. / self.nobs
                    else:
                        scale_covariance = 1.
            elif all(getattr(obs, 'covariance', None) is not None for obs in self.observables):
                covariances = [obs.covariance for obs in self.observables]
                size = sum(cov.shape[0] for cov in covariances)
                covariance = np.zeros((size, size), dtype='f8')
                start = 0
                for cov in covariances:
                    stop = start + cov.shape[0]
                    sl = slice(start, stop)
                    covariance[sl, sl] = cov
                    start = stop
            else:
                raise ValueError('Observables must have mocks if global covariance matrix not provided')
        if isinstance(scale_covariance, bool):
            import warnings
            if scale_covariance:
                warnings.warn('Got scale_covariance = {} (boolean), but I do not know the number of realizations; defaults to scale_covariance = 1.'.format(scale_covariance))
            else:
                warnings.warn('Got scale_covariance = {} (boolean), why? defaulting to scale_covariance = 1.'.format(scale_covariance))
            scale_covariance = 1.
        self.covariance = np.atleast_2d(self.mpicomm.bcast(scale_covariance * covariance if self.mpicomm.rank == 0 else None, root=0))
        if self.covariance.shape != (self.covariance.shape[0],) * 2:
            raise ValueError('Covariance must be a square matrix')
        self.flatdata = np.concatenate([obs.flatdata for obs in self.observables], axis=0)
        if self.covariance.shape != (self.flatdata.size,) * 2:
            raise ValueError('Based on provided observables, covariance expected to be a matrix of shape ({0:d}, {0:d})'.format(self.flatdata.size))

        # Set each observable's covariance (for, e.g., plots)
        start, slices = 0, []
        for obs in observables:
            stop = start + len(obs.flatdata)
            sl = slice(start, stop)
            slices.append(sl)
            obs.covariance = self.covariance[sl, sl]
            start = stop

        # Block-inversion is usually more numerically stable
        self.precision = utils.blockinv([[self.covariance[sl1, sl2] for sl2 in slices] for sl1 in slices])
        size = self.precision.shape[0]
        if self.nobs is not None:
            self.hartlap = (self.nobs - size - 2.) / (self.nobs - 1.)
            if self.mpicomm.rank == 0:
                self.log_info('Covariance matrix with {:d} points built from {:d} observations.'.format(size, self.nobs))
                self.log_info('...resulting in Hartlap factor of {:.4f}.'.format(self.hartlap))
            self.precision *= self.hartlap
        BaseLikelihood.initialize(self)
        self.runtime_info.requires = self.observables

    @property
    def flattheory(self):
        return jnp.concatenate([obs.flattheory for obs in self.observables], axis=0)


# For backward-compatibility
GaussianLikelihood = ObservablesGaussianLikelihood


class SumLikelihood(BaseLikelihood):

    _attrs = ['loglikelihood', 'logprior']

    def initialize(self, likelihoods):
        if not utils.is_sequence(likelihoods): likelihoods = [likelihoods]
        self.likelihoods = list(likelihoods)

        def _make_solve(likelihood):

            def _solve():
                return likelihood.loglikelihood

            return _solve

        # Deactivate likelihood _solve(), as self._solve() will take care of everything
        for likelihood in self.likelihoods:
            setattr(likelihood, '_solve', _make_solve(likelihood))

        super(SumLikelihood, self).initialize()
        self.runtime_info.requires = self.likelihoods

    def calculate(self):
        self.loglikelihood = sum(likelihood.loglikelihood for likelihood in self.likelihoods)

    def get(self):
        return self._solve()

    def _solve(self):
        return BaseGaussianLikelihood._solve(self)
