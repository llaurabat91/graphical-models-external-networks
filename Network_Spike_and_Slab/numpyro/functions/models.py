#%%
import my_utils
import jax
import numpyro
numpyro.set_platform('cpu')
print(jax.lib.xla_bridge.get_backend().platform)
import jax.numpy as jnp
import jax.nn as nn
from numpyro import plate, sample,  factor
import numpyro.distributions as dist
from numpyro.distributions import ImproperUniform, constraints
import numpyro.infer.util 
from numpyro.primitives import deterministic
from numpyro.util import enable_x64

#%%
enable_x64(use_x64=True)
print("Is 64 precision enabled?:", jax.config.jax_enable_x64)

#%%
def glasso_repr(eta1_0_m=0., eta1_0_s=5., mu_m=0., mu_s=1., Y=None, n=None, p=None):
    try:
        n, p = jnp.shape(Y)
    except:
         assert ((n is None)|(p is None)) is False
    
    with plate("features", p):
        mu = sample("mu", dist.Normal(mu_m, mu_s))
        sqrt_diag = sample("sqrt_diag", dist.InverseGamma(1., 0.5))

    eta1_0 = sample("eta1_0", dist.Normal(eta1_0_m, eta1_0_s))
    
    tril_idx = jnp.tril_indices(n=p, k=-1, m=p)
    tril_len = tril_idx[0].shape[0]
    rho_tilde = numpyro.sample("rho_tilde", dist.Laplace(0., 1.).expand((tril_len,)))
    
    rho_lt = numpyro.deterministic("rho_lt", rho_tilde*jnp.exp(-eta1_0))
    rho_mat_tril = jnp.zeros((p,p))
    rho_mat_tril = rho_mat_tril.at[tril_idx].set(rho_lt)
    rho = rho_mat_tril + rho_mat_tril.T + jnp.identity(p)
    
    factor("rho_factor", (ImproperUniform(constraints.corr_matrix, (), event_shape=(p,p)).log_prob(rho)).sum())
    rho = deterministic("rho", rho)

    
    theta = jnp.outer(sqrt_diag,sqrt_diag)*rho
    theta = deterministic("theta", theta)

    with plate("hist", n):
        Y = sample("obs", dist.MultivariateNormal(mu, precision_matrix=theta), obs = Y)
        
    return {'Y':Y, 'theta_true':theta, 'mu_true':mu, 'eta1_0_true':eta1_0}


#%%
def glasso_ss_repr(eta0_0_m=0., eta0_0_s=2., eta1_0_m=-7., eta1_0_s=2., eta2_0_m=0., eta2_0_s=1.,
              mu_m=0., mu_s=1., Y=None, n=None, p=None):
    try:
        n, p = jnp.shape(Y)
    except:
         assert ((n is None)|(p is None)) is False
    
    with plate("features", p):
        mu = sample("mu", dist.Normal(mu_m, mu_s))
        sqrt_diag = sample("sqrt_diag", dist.InverseGamma(0.01, 0.01))
        
    eta0_0 = sample("eta0_0", dist.Normal(eta0_0_m, eta0_0_s))
    mean_slab = deterministic("mean_slab", eta0_0)

    scale_spike = sample("scale_spike", dist.InverseGamma(10, 0.5))
    eta1_0 = sample("eta1_0", dist.Normal(eta1_0_m, eta1_0_s))
    scale_slab = scale_spike*(1+jnp.exp(-eta1_0))
    scale_slab = deterministic("scale_slab", scale_slab)
    
    tril_idx = jnp.tril_indices(n=p, k=-1, m=p)
    tril_len = tril_idx[0].shape[0]
    
    eta2_0 = sample("eta2_0", dist.Normal(eta2_0_m, eta2_0_s))
    w_slab = (1+jnp.exp(-eta2_0))**(-1)
    w_slab = deterministic("w_slab", w_slab)
    
    u = sample("u", dist.Uniform(0.0, 1.0).expand((tril_len, )))
    # is_spike = my_utils.my_sigmoid(u, beta=500., alpha=w_slab)
    is_spike = my_utils.my_sigmoid(u, beta=100., alpha=w_slab)
    
    rho_tilde = numpyro.sample("rho_tilde", dist.Laplace(0., 1.).expand((tril_len,)))
    rho_lt = numpyro.deterministic("rho_lt", is_spike*rho_tilde*scale_spike + 
                                  (1-is_spike)*(rho_tilde*scale_slab + mean_slab))
    
    rho_mat_tril = jnp.zeros((p,p))
    rho_mat_tril = rho_mat_tril.at[tril_idx].set(rho_lt)
    rho = rho_mat_tril + rho_mat_tril.T + jnp.identity(p)
    
    factor("rho_factor", (ImproperUniform(constraints.corr_matrix, (), event_shape=(p,p)).log_prob(rho)).sum())
    rho = deterministic("rho", rho)

    ####
    
    theta = jnp.outer(sqrt_diag,sqrt_diag)*rho
    theta = deterministic("theta", theta)

    with plate("hist", n):
        Y = sample("obs", dist.MultivariateNormal(mu, precision_matrix=theta), obs = Y)
        
    return {'Y':Y, 'theta_true':theta, 'mu_true':mu, 'scale_spike_true':scale_spike}
#%%
def NetworkSS_repr(A_list, eta0_0_m=0., eta0_0_s=5., eta1_0_m=0., eta1_0_s=5., eta2_0_m=0., eta2_0_s=5.,
              eta0_coefs_m=0., eta0_coefs_s=5., eta1_coefs_m=0., eta1_coefs_s=5., eta2_coefs_m=0., eta2_coefs_s=5., 
           mu_m=0., mu_s=1., Y=None, n=None, p=None):

    try:
        n, p = jnp.shape(Y)
    except:
         assert ((n is None)|(p is None)) is False
    
    # intercepts
    eta0_0 = sample("eta0_0", dist.Normal(eta0_0_m, eta0_0_s))     
    eta1_0 = sample("eta1_0", dist.Normal(eta1_0_m, eta1_0_s))
    eta2_0 = sample("eta2_0", dist.Normal(eta2_0_m, eta2_0_s))
    
    # coefs
    a = len(A_list)

    assert ((a>0))
    eta0_coefs = sample("eta0_coefs", dist.Normal(eta0_coefs_m, eta0_coefs_s).expand((a,))) # (a,)
    eta1_coefs = sample("eta1_coefs", dist.Normal(eta1_coefs_m, eta1_coefs_s).expand((a,))) # (a,)
    eta2_coefs = sample("eta2_coefs", dist.Normal(eta2_coefs_m, eta2_coefs_s).expand((a,))) # (a,)

    with plate("features", p):
        mu = sample("mu", dist.Normal(mu_m, mu_s))
        sqrt_diag = sample("sqrt_diag", dist.InverseGamma(0.01, 0.01))
    
    
    # means
    tril_idx = jnp.tril_indices(n=p, k=-1, m=p)
    tril_len = tril_idx[0].shape[0]
    A_tril_arr = jnp.array([A[tril_idx] for A in A_list]) # (a, p, p)

    A_tril_mean0 = 0.
    for coef, A in zip(eta0_coefs,A_tril_arr):
        A_tril_mean0 += coef*A
    A_tril_mean0 = deterministic("A_tril_mean0", A_tril_mean0)

    A_tril_mean1 = 0.
    for coef, A in zip(eta1_coefs,A_tril_arr):
        A_tril_mean1 += coef*A
    A_tril_mean1 = deterministic("A_tril_mean1", A_tril_mean1)
        
    A_tril_mean2 = 0.
    for coef, A in zip(eta2_coefs,A_tril_arr):
        A_tril_mean2 += coef*A
    A_tril_mean2 = deterministic("A_tril_mean2", A_tril_mean2)
    
    # scale spike
    scale_spike = sample("scale_spike", dist.InverseGamma(10, 0.5))
    scale_spike = jnp.ones((tril_len,))*scale_spike
    
    # mean slab
    mean_slab = eta0_0+A_tril_mean0
    mean_slab = deterministic("mean_slab", mean_slab)
    
    # scale slab
    scale_slab = scale_spike*(1+jnp.exp(-eta1_0-A_tril_mean1))
    scale_slab = deterministic("scale_slab", scale_slab)
    
    # prob of being in the slab
    w_slab = 1/(1+jnp.exp(-eta2_0 -A_tril_mean2)) # 45
    w_slab = deterministic("w_slab", w_slab)
    
    
    u = sample("u", dist.Uniform(0.0, 1.0).expand((tril_len, )))
    is_spike = my_utils.my_sigmoid(u, beta=500., alpha=w_slab)
    
    # corr mat
    rho_tilde = numpyro.sample("rho_tilde", dist.Laplace(0., 1.).expand((tril_len,)))
    rho_lt = numpyro.deterministic("rho_lt", is_spike*rho_tilde*scale_spike + 
                                  (1-is_spike)*(rho_tilde*scale_slab + mean_slab))
    
    rho_mat_tril = jnp.zeros((p,p))
    rho_mat_tril = rho_mat_tril.at[tril_idx].set(rho_lt)
    rho = rho_mat_tril + rho_mat_tril.T + jnp.identity(p)
    
    factor("rho_factor", (ImproperUniform(constraints.corr_matrix, (), event_shape=(p,p)).log_prob(rho)).sum())
    rho = deterministic("rho", rho)
    
    theta = jnp.outer(sqrt_diag,sqrt_diag)*rho
    theta = deterministic("theta", theta)

    with plate("hist", n):
        Y = sample("obs", dist.MultivariateNormal(mu, precision_matrix=theta), obs = Y)
    

    return {'Y':Y, 'theta':theta, 'mu':mu, 'rho':rho, 'eta1_0':eta1_0, 'eta1_coefs':eta1_coefs}

#%%

def logprior_NetworkSS(scale_spike, scale_slab, mean_slab, w_slab, rho_lt):

    w_spike = 1-w_slab # 45

    log_spike = dist.Laplace(0., scale_spike).log_prob(rho_lt)

    log_slab = dist.Laplace(mean_slab, scale_slab).log_prob(rho_lt)
    
    probs = jnp.hstack([jnp.array([jnp.log(w_spike)+log_spike])[:,None],
    jnp.array([jnp.log(w_slab)+log_slab])[:,None]])
    logprobs = nn.logsumexp(probs, axis=1)

    logprobs = logprobs.sum()
    
    return logprobs

#%%
def glasso_ss_repr_etaRepr(eta0_0_m=0., eta0_0_s=2., eta1_0_m=-7., eta1_0_s=2., eta2_0_m=0., eta2_0_s=1.,
              mu_m=0., mu_s=1., Y=None, n=None, p=None):
    try:
        n, p = jnp.shape(Y)
    except:
         assert ((n is None)|(p is None)) is False
    
    with plate("features", p):
        mu = sample("mu", dist.Normal(mu_m, mu_s))
        sqrt_diag = sample("sqrt_diag", dist.InverseGamma(0.01, 0.01))
        
    tilde_eta0_0 = sample("tilde_eta0_0", dist.Normal(0, jnp.sqrt((p*(p-1)/2.0)/n)))   
    eta0_0 = eta0_0_m + eta0_0_s * tilde_eta0_0 / jnp.sqrt((p*(p-1)/2.0)/n)
    eta0_0 = deterministic("eta0_0", eta0_0)
    mean_slab = deterministic("mean_slab", eta0_0)

    scale_spike = sample("scale_spike", dist.InverseGamma(10, 0.5))
    tilde_eta1_0 = sample("tilde_eta1_0", dist.Normal(0, jnp.sqrt((p*(p-1)/2.0)/n)))
    eta1_0 = eta1_0_m + eta1_0_s * tilde_eta1_0 / jnp.sqrt((p*(p-1)/2.0)/n)
    eta1_0 = deterministic("eta1_0", eta1_0)  
    scale_slab = scale_spike*(1+jnp.exp(-eta1_0))
    scale_slab = deterministic("scale_slab", scale_slab)
    
    tril_idx = jnp.tril_indices(n=p, k=-1, m=p)
    tril_len = tril_idx[0].shape[0]
    
    tilde_eta2_0 = sample("tilde_eta2_0", dist.Normal(0, jnp.sqrt((p*(p-1)/2.0)/n)))
    eta2_0 = eta2_0_m + eta2_0_s * tilde_eta2_0 / jnp.sqrt((p*(p-1)/2.0)/n)
    eta2_0 = deterministic("eta2_0", eta2_0)    
    w_slab = (1+jnp.exp(-eta2_0))**(-1)
    w_slab = deterministic("w_slab", w_slab)
    
    u = sample("u", dist.Uniform(0.0, 1.0).expand((tril_len, )))
    is_spike = my_utils.my_sigmoid(u, beta=100., alpha=w_slab)
    
    rho_tilde = numpyro.sample("rho_tilde", dist.Laplace(0., 1.).expand((tril_len,)))
    rho_lt = numpyro.deterministic("rho_lt", is_spike*rho_tilde*scale_spike + 
                                  (1-is_spike)*(rho_tilde*scale_slab + mean_slab))
    
    rho_mat_tril = jnp.zeros((p,p))
    rho_mat_tril = rho_mat_tril.at[tril_idx].set(rho_lt)
    rho = rho_mat_tril + rho_mat_tril.T + jnp.identity(p)
    
    factor("rho_factor", (ImproperUniform(constraints.corr_matrix, (), event_shape=(p,p)).log_prob(rho)).sum())
    rho = deterministic("rho", rho)

    ####
    
    theta = jnp.outer(sqrt_diag,sqrt_diag)*rho
    theta = deterministic("theta", theta)

    with plate("hist", n):
        Y = sample("obs", dist.MultivariateNormal(mu, precision_matrix=theta), obs = Y)
        
    return {'Y':Y, 'theta_true':theta, 'mu_true':mu, 'scale_spike_true':scale_spike}
#%%
def NetworkSS_repr_etaRepr(A_list, eta0_0_m=0., eta0_0_s=5., eta1_0_m=0., eta1_0_s=5., eta2_0_m=0., eta2_0_s=5.,
              eta0_coefs_m=0., eta0_coefs_s=5., eta1_coefs_m=0., eta1_coefs_s=5., eta2_coefs_m=0., eta2_coefs_s=5., 
           mu_m=0., mu_s=1., Y=None, n=None, p=None):

    try:
        n, p = jnp.shape(Y)
    except:
         assert ((n is None)|(p is None)) is False
    
    # intercepts
    tilde_eta0_0 = sample("tilde_eta0_0", dist.Normal(0, jnp.sqrt((p*(p-1)/2.0)/n)))     
    tilde_eta1_0 = sample("tilde_eta1_0", dist.Normal(0, jnp.sqrt((p*(p-1)/2.0)/n)))
    tilde_eta2_0 = sample("tilde_eta2_0", dist.Normal(0, jnp.sqrt((p*(p-1)/2.0)/n)))
    
    eta0_0 = eta0_0_m + eta0_0_s * tilde_eta0_0 / jnp.sqrt((p*(p-1)/2.0)/n)
    eta0_0 = deterministic("eta0_0", eta0_0)
    eta1_0 = eta1_0_m + eta1_0_s * tilde_eta1_0 / jnp.sqrt((p*(p-1)/2.0)/n)
    eta1_0 = deterministic("eta1_0", eta1_0)    
    eta2_0 = eta2_0_m + eta2_0_s * tilde_eta2_0 / jnp.sqrt((p*(p-1)/2.0)/n)
    eta2_0 = deterministic("eta2_0", eta2_0)    
    
    # coefs
    a = len(A_list)

    assert ((a>0))
    tilde_eta0_coefs = sample("tilde_eta0_coefs", dist.Normal(0, jnp.sqrt((p*(p-1)/2.0)/n)).expand((a,))) # (a,)
    tilde_eta1_coefs = sample("tilde_eta1_coefs", dist.Normal(0, jnp.sqrt((p*(p-1)/2.0)/n)).expand((a,))) # (a,)
    tilde_eta2_coefs = sample("tilde_eta2_coefs", dist.Normal(0, jnp.sqrt((p*(p-1)/2.0)/n)).expand((a,))) # (a,)
    
    eta0_coefs = eta0_coefs_m + eta0_coefs_s * tilde_eta0_coefs / jnp.sqrt((p*(p-1)/2.0)/n)
    eta0_coefs = deterministic("eta0_coefs", eta0_coefs)
    eta1_coefs = eta1_coefs_m + eta1_coefs_s * tilde_eta1_coefs / jnp.sqrt((p*(p-1)/2.0)/n)
    eta1_coefs = deterministic("eta1_coefs", eta1_coefs)    
    eta2_coefs = eta2_coefs_m + eta2_coefs_s * tilde_eta2_coefs / jnp.sqrt((p*(p-1)/2.0)/n)
    eta2_coefs = deterministic("eta2_coefs", eta2_coefs) 
    assert (len(eta0_coefs) == a) 

    with plate("features", p):
        mu = sample("mu", dist.Normal(mu_m, mu_s))
        sqrt_diag = sample("sqrt_diag", dist.InverseGamma(0.01, 0.01))
    
    
    # means
    tril_idx = jnp.tril_indices(n=p, k=-1, m=p)
    tril_len = tril_idx[0].shape[0]
    A_tril_arr = jnp.array([A[tril_idx] for A in A_list]) # (a, p, p)

    A_tril_mean0 = 0.
    for coef, A in zip(eta0_coefs,A_tril_arr):
        A_tril_mean0 += coef*A
    A_tril_mean0 = deterministic("A_tril_mean0", A_tril_mean0)

    A_tril_mean1 = 0.
    for coef, A in zip(eta1_coefs,A_tril_arr):
        A_tril_mean1 += coef*A
    A_tril_mean1 = deterministic("A_tril_mean1", A_tril_mean1)
        
    A_tril_mean2 = 0.
    for coef, A in zip(eta2_coefs,A_tril_arr):
        A_tril_mean2 += coef*A
    A_tril_mean2 = deterministic("A_tril_mean2", A_tril_mean2)
    
    # scale spike
    scale_spike = sample("scale_spike", dist.InverseGamma(10, 0.5))
    scale_spike = jnp.ones((tril_len,))*scale_spike
    
    # mean slab
    mean_slab = eta0_0+A_tril_mean0
    mean_slab = deterministic("mean_slab", mean_slab)
    
    # scale slab
    scale_slab = scale_spike*(1+jnp.exp(-eta1_0-A_tril_mean1))
    scale_slab = deterministic("scale_slab", scale_slab)
    
    # prob of being in the slab
    w_slab = 1/(1+jnp.exp(-eta2_0 -A_tril_mean2)) # 45
    w_slab = deterministic("w_slab", w_slab)
    
    
    u = sample("u", dist.Uniform(0.0, 1.0).expand((tril_len, )))
    is_spike = my_utils.my_sigmoid(u, beta=100., alpha=w_slab)
    
    # corr mat
    rho_tilde = numpyro.sample("rho_tilde", dist.Laplace(0., 1.).expand((tril_len,)))
    rho_lt = numpyro.deterministic("rho_lt", is_spike*rho_tilde*scale_spike + 
                                  (1-is_spike)*(rho_tilde*scale_slab + mean_slab))
    
    rho_mat_tril = jnp.zeros((p,p))
    rho_mat_tril = rho_mat_tril.at[tril_idx].set(rho_lt)
    rho = rho_mat_tril + rho_mat_tril.T + jnp.identity(p)
    
    factor("rho_factor", (ImproperUniform(constraints.corr_matrix, (), event_shape=(p,p)).log_prob(rho)).sum())
    rho = deterministic("rho", rho)
    
    theta = jnp.outer(sqrt_diag,sqrt_diag)*rho
    theta = deterministic("theta", theta)

    with plate("hist", n):
        Y = sample("obs", dist.MultivariateNormal(mu, precision_matrix=theta), obs = Y)
    

    return {'Y':Y, 'theta':theta, 'mu':mu, 'rho':rho, 'eta1_0':eta1_0, 'eta1_coefs':eta1_coefs}

#%%
