# Mathematics of the RL source scheduler

[Documentation index](document.md) · [Implementation guide](rl-scheduler.md)

This chapter gives the complete mathematical model behind the adaptive
job-source scheduler. It separates the general reinforcement-learning
formulation from the exact equations implemented in this repository.

The scheduler does not rank jobs or relax eligibility rules. Its only decision
is whether to launch another bounded wave of sources or stop collecting and
return the candidates accumulated so far.

## 1. Sequential decision problem

Let the finite, ordered source set be

$$
\mathcal{J}=\{J_1,J_2,\ldots,J_N\}.
$$

The scheduler decides after each concurrent wave finishes. With $k$ denoting a
decision point, an episode is

$$
S_0\xrightarrow{A_0,R_1}S_1\xrightarrow{A_1,R_2}\cdots
\xrightarrow{A_{K-1},R_K}S_K.
$$

A wave has variable duration $\tau_k=T_{k+1}-T_k$. The most precise general
description is therefore a finite-horizon semi-Markov decision process. The
implementation includes elapsed time in the state and applies ordinary
discrete-transition Q-learning at wave boundaries.

An MDP is

$$
\mathcal{M}=(\mathcal{S},\mathcal{A},P,R,\gamma),
$$

where $\mathcal{S}$ is the state space, $\mathcal{A}$ the action space,
$P(s'\mid s,a)$ the unknown transition distribution, $R(s,a,s')$ the reward,
and $\gamma\in[0,1]$ the discount factor.

A duration-aware semi-MDP could discount with $\gamma^{\tau_k}$. The current
code instead uses one discount step per recorded transition:

$$
\widehat{Y}_k=R_{k+1}+\gamma\max_{a'}Q(S_{k+1},a').
$$

## 2. Exact observable state

The raw state is

$$
S_k=(t_k,F_k,Y_k,C_k,E_k,A_k^{\mathrm{active}},M_k),
$$

where:

| Symbol | Code field | Meaning |
|---|---|---|
| $t_k$ | `elapsed_seconds` | elapsed scheduling time |
| $F_k$ | `fetched_jobs` | all fetched listings |
| $Y_k$ | `eligible_jobs` | listings passing every mandatory gate |
| $C_k$ | `completed_agents` | completed source agents |
| $E_k$ | `failed_agents` | failed source agents |
| $A_k^{\mathrm{active}}$ | `active_agents` | running source agents |
| $M_k$ | `remaining_agents` | sources not yet launched |

Eligibility is calculated outside RL:

$$
Y_k=g(\mathcal{D}_k;\theta),
$$

where $\mathcal{D}_k$ is the accumulated listing set and $\theta$ contains the
country, age, search type, education, salary, and relevance constraints. The
policy cannot modify $g$ or $\theta$.

## 3. State discretization

Tabular Q-learning needs finite keys. The raw state is mapped by

$$
\phi(S_k)=
\left(b_t(t_k),b_y(Y_k),b_m(M_k),b_e(E_k),
b_a(A_k^{\mathrm{active}})\right),
$$

where

$$
b_t(t)=\min\left(5,\left\lfloor\frac{t}{3}\right\rfloor\right),
\qquad
b_y(Y)=\min\left(5,\left\lfloor\frac{Y}{3}\right\rfloor\right),
$$

$$
b_m(M)=\min(5,M),\qquad
b_e(E)=\min(2,E),\qquad
b_a(A)=\min(3,A).
$$

It is serialized as:

```text
t{time}|e{eligible}|r{remaining}|f{failures}|a{active}
```

For $t=7.4$, $Y=8$, $M=3$, $E=0$, and $A=0$:

$$
b_t=\lfloor7.4/3\rfloor=2,\qquad
b_y=\lfloor8/3\rfloor=2,
$$

so the key is `t2|e2|r3|f0|a0`.

Ignoring impossible combinations, the maximum table size is

$$
6\times6\times6\times3\times4=2592\text{ states},
$$

or at most

$$
2592\times2=5184
$$

state-action values. $F_k$ and $C_k$ remain in audit traces but are omitted
from the table key. Bucketing reduces the training-data requirement but aliases
raw states that may have different future source yields.

## 4. Action space and wave size

The action space is

$$
\mathcal{A}=
\{\texttt{launch\_next},\texttt{stop\_launching}\}.
$$

Feasible actions are

$$
\mathcal{A}(S_k)=
\begin{cases}
\{\texttt{launch\_next},\texttt{stop\_launching}\},&M_k>0,\\
\{\texttt{stop\_launching}\},&M_k=0.
\end{cases}
$$

With parallel capacity $B$, `launch_next` launches

$$
L_k=\min(B,M_k)
$$

sources. The learned action does not select their identities; source order is
deterministic. `stop_launching` terminates source collection and passes the
accumulated jobs to deterministic ranking.

## 5. Policy and exploration

A stochastic policy is

$$
\pi(a\mid s)=\Pr(A_k=a\mid S_k=s).
$$

Learned live inference is greedy:

$$
\pi(s)=\arg\max_{a\in\mathcal{A}(s)}Q(s,a).
$$

An exact Q-value tie is resolved in favor of `stop_launching`. For offline
exploration, epsilon-greedy behavior is

$$
\pi_\epsilon(a\mid s)=
\begin{cases}
1-\epsilon+\epsilon/|\mathcal{A}(s)|,&a=a^*,\\
\epsilon/|\mathcal{A}(s)|,&a\ne a^*,
\end{cases}
$$

where $a^*=\arg\max_aQ(s,a)$. Live execution explicitly uses $\epsilon=0$ and
`explore=False`; user searches are never randomly explored.

## 6. Return and value functions

The discounted return is

$$
G_k=\sum_{j=0}^{K-k-1}\gamma^jR_{k+j+1}.
$$

The value functions are

$$
V^\pi(s)=\mathbb{E}_\pi[G_k\mid S_k=s],
$$

$$
Q^\pi(s,a)=\mathbb{E}_\pi[G_k\mid S_k=s,A_k=a].
$$

The optimal value and policy are

$$
Q^*(s,a)=\max_\pi Q^\pi(s,a),
\qquad
\pi^*(s)=\arg\max_aQ^*(s,a).
$$

## 7. Bellman equations

For a fixed policy:

$$
Q^\pi(s,a)=
\sum_{s'}P(s'\mid s,a)
\left[
R(s,a,s')+
\gamma\sum_{a'}\pi(a'\mid s')Q^\pi(s',a')
\right].
$$

The Bellman optimality equation is

$$
Q^*(s,a)=
\sum_{s'}P(s'\mid s,a)
\left[
R(s,a,s')+\gamma\max_{a'}Q^*(s',a')
\right].
$$

Source latency, failure, and eligible yield are unknown, so Q-learning
estimates values from transitions without explicitly learning $P$.

## 8. Exact implemented reward

Define

$$
\Delta Y_k=\max(0,Y_{k+1}-Y_k),
\qquad
\Delta t_k=\max(0,t_{k+1}-t_k).
$$

Let $I_k^L\in\{0,1\}$ indicate that a source was launched and
$I_k^F\in\{0,1\}$ indicate a source failure. The implemented reward is

$$
R_{k+1}=w_y\Delta Y_k-w_t\Delta t_k-w_cI_k^L-w_fI_k^F.
$$

With defaults $w_y=2$, $w_t=0.05$, $w_c=0.20$, and $w_f=1$:

$$
\boxed{
R_{k+1}=2\Delta Y_k-0.05\Delta t_k-0.20I_k^L-I_k^F
}.
$$

One verified job contributes $+2$, equivalent on the reward scale to:

$$
\frac{2}{0.05}=40\text{ seconds},\qquad
\frac{2}{0.20}=10\text{ launch indicators},\qquad
\frac{2}{1}=2\text{ failure indicators}.
$$

These coefficient ratios encode designer preferences; they are not learned.

### Exact limitation of the Boolean penalties

The runner can launch $L_k>1$ sources in one wave, while the reward accepts a
Boolean launch indicator. A one-source and two-source wave can therefore both
incur $0.20$. The failure term is likewise Boolean, not a failure count.

A count-sensitive generalization would be

$$
\widetilde R_{k+1}
=w_y\Delta Y_k-w_t\Delta t_k-w_cL_k-w_f(E_{k+1}-E_k),
$$

but this is not the exact current implementation.

There is deliberately no reward for $\Delta F_k$. A noisy source should not
benefit merely by returning many irrelevant listings.

## 9. Q-learning update

For a nonterminal transition $(S_k,A_k,R_{k+1},S_{k+1})$, the temporal-
difference target and error are

$$
\widehat Y_k=
R_{k+1}+\gamma\max_{a'}Q(S_{k+1},a'),
$$

$$
\delta_k=\widehat Y_k-Q(S_k,A_k).
$$

The complete update is

$$
\boxed{
Q(S_k,A_k)\leftarrow Q(S_k,A_k)+
\alpha\left[
R_{k+1}+\gamma\max_{a'}Q(S_{k+1},a')-Q(S_k,A_k)
\right]
}.
$$

Defaults are $\alpha=0.20$ and $\gamma=0.90$. For a terminal transition, the
future term is zero:

$$
Q(S_k,A_k)\leftarrow
Q(S_k,A_k)+\alpha[R_{k+1}-Q(S_k,A_k)].
$$

Q-learning is off-policy because its target uses
$\max_{a'}Q(S_{k+1},a')$, not necessarily the next action selected by the
behavior policy. SARSA would instead use

$$
R_{k+1}+\gamma Q(S_{k+1},A_{k+1}),
$$

which this project does not implement.

## 10. Complete numerical update

Suppose $Y_k=7$, $t_k=4.2$, $Y_{k+1}=12$, $t_{k+1}=7.1$, a source was
launched, and no source failed. Then

$$
\Delta Y_k=5,\qquad\Delta t_k=2.9,
$$

and

$$
R_{k+1}=2(5)-0.05(2.9)-0.20=9.655.
$$

If the old value is $Q(S_k,\texttt{launch\_next})=3$ and the best next-state
value is $4$, then

$$
\widehat Y_k=9.655+0.90(4)=13.255,
$$

$$
\delta_k=13.255-3=10.255,
$$

and

$$
Q_{\mathrm{new}}=3+0.20(10.255)=5.051.
$$

For a terminal failed transition with no eligible gain, eight seconds of
latency, and old value $1.5$:

$$
R=-0.05(8)-0.20-1=-1.60,
$$

$$
Q_{\mathrm{new}}=1.5+0.20(-1.60-1.5)=0.88.
$$

Productive transitions increase the launch value; repeated slow or failed
transitions decrease it.

## 11. Deterministic cold-start policy

Let $Y_{\min}$ be the minimum result floor, $Y_{\mathrm{target}}$ the target,
$T_s$ the soft deadline, and $T_h$ the hard deadline. An unseen state uses

$$
\pi_0(S_k)=
\begin{cases}
\texttt{stop\_launching},&M_k=0,\\
\texttt{stop\_launching},&Y_k\ge Y_{\mathrm{target}},\\
\texttt{stop\_launching},&t_k\ge T_s\land Y_k\ge Y_{\min},\\
\texttt{launch\_next},&\text{otherwise}.
\end{cases}
$$

The code also checks $t_k\ge T_h\land Y_k\ge Y_{\min}$. Since
$0<T_s\le T_h$, this is logically implied by the preceding soft-deadline
condition. The runner repeats a hard-deadline override outside the policy.

The important fallback invariant is

$$
Y_k<Y_{\min}\land M_k>0
\Longrightarrow
\pi_0(S_k)=\texttt{launch\_next}.
$$

Time alone cannot make the fallback stop with too few verified jobs.

For a learned table entry, however, the minimum-result continuation rule is
not a universal override: a learned Q-table can select `stop_launching` below
$Y_{\min}$. This is why empty-result and recall promotion gates are necessary.

## 12. Termination proof

Every launch removes at least one source:

$$
M_{k+1}<M_k,\qquad 0\le M_k\le N.
$$

With wave capacity $B$, no more than

$$
\left\lceil\frac{N}{B}\right\rceil
$$

waves are required to exhaust all sources. The scheduler therefore cannot
create an infinite launch sequence, assuming external calls eventually return
or fail.

## 13. Parallel-wave latency

If source $j$ in wave $k$ takes $\tau_{k,j}$ seconds, complete-wave waiting
gives

$$
\tau_k^{\mathrm{wave}}=\max_{j\in W_k}\tau_{k,j},
$$

not the sum of source durations. Approximate adaptive latency is

$$
T_{\mathrm{adaptive}}
=\sum_{k=1}^{K}\max_{j\in W_k}\tau_{k,j}.
$$

Launching every source concurrently has approximate latency

$$
T_{\mathrm{full}}=\max_{j\in\mathcal{J}}\tau_j.
$$

Adaptive execution is faster only when skipped sources would extend the
critical path enough to compensate for sequential wave boundaries. Fewer calls
do not mathematically guarantee lower latency.

## 14. Constrained optimization interpretation

Let $C^\pi$ be source calls, $T^\pi$ latency, and
$Q_{\mathrm{rank}}^\pi$ ranking quality. Deployment can be viewed as

$$
\min_\pi\quad
\lambda_T\mathbb{E}[T^\pi]+\lambda_C\mathbb{E}[C^\pi]
$$

subject to

$$
\mathbb{E}[Q_{\mathrm{rank}}^\pi]
\ge
\mathbb{E}[Q_{\mathrm{rank}}^b]-\varepsilon_Q,
$$

$$
\Pr(Y^\pi=0)\le\Pr(Y^b=0),
$$

plus every deterministic eligibility rule. The scalar immediate reward
approximates this multi-objective problem; it cannot prove those constraints.

## 15. Evaluation mathematics

For binary relevance:

$$
\operatorname{Precision@K}
=\frac{1}{K}\sum_{i=1}^{K}\operatorname{rel}_i,
$$

$$
\operatorname{Recall@K}
=\frac{\sum_{i=1}^{K}\operatorname{rel}_i}
{\sum_{d\in\mathcal{D}}\operatorname{rel}(d)}.
$$

For graded labels:

$$
\operatorname{DCG@K}
=\sum_{i=1}^{K}
\frac{2^{\operatorname{rel}_i}-1}{\log_2(i+1)},
$$

$$
\operatorname{NDCG@K}
=\frac{\operatorname{DCG@K}}{\operatorname{IDCG@K}}.
$$

The promotion constraints are

$$
\operatorname{NDCG@10}_\pi
\ge
\operatorname{NDCG@10}_b-0.01,
$$

$$
\operatorname{Recall@50}_\pi
\ge
\operatorname{Recall@50}_b-0.02.
$$

For paired baseline and policy latencies:

$$
\Delta_T=
100\left(
1-\frac{\operatorname{median}(T^\pi)}
{\operatorname{median}(T^b)}
\right),
$$

with required $\Delta_T\ge20\%$. Mean call reduction is

$$
\Delta_C=
100\left(1-\frac{\bar C_\pi}{\bar C_b}\right),
$$

with required $\Delta_C\ge25\%$. A reduction from five calls to two is

$$
100(1-2/5)=60\%.
$$

These metrics are evaluation constraints, not direct terms in the current
reward.

## 16. Convergence conditions and limitations

Classical tabular Q-learning converges to $Q^*$ under assumptions including a
stationary finite MDP, bounded rewards, infinite visits to every state-action
pair, and learning rates satisfying

$$
\sum_{n=1}^{\infty}\alpha_n=\infty,
\qquad
\sum_{n=1}^{\infty}\alpha_n^2<\infty.
$$

The fixed $\alpha=0.20$ does not satisfy diminishing-step conditions over an
infinite sequence, and live job sources are nonstationary. This project
therefore has no formal convergence guarantee. Replay evaluation supplies
empirical evidence, not a proof of optimality.

The Markov property would require

$$
\Pr(S_{k+1}\mid S_0,A_0,\ldots,S_k,A_k)
=
\Pr(S_{k+1}\mid S_k,A_k).
$$

The bucket omits source identities, query topic, country, per-source history,
fetched count, and rate-limit conditions. Equal buckets can therefore have
different future-yield distributions. After this compression, the practical
problem is partially observed and state-aliased.

## 17. Training, inference, and fallback

These are three distinct regimes.

For an unseen state:

$$
Q(\phi(S_k),\cdot)\text{ absent}
\Longrightarrow
A_k=\pi_0(S_k).
$$

For learned live inference:

$$
A_k=
\arg\max_{a\in\mathcal{A}(S_k)}Q(\phi(S_k),a),
\qquad\epsilon=0.
$$

For offline learning:

$$
Q\leftarrow Q+\alpha[R+\gamma\max Q'-Q].
$$

The live runner calls `choose(..., explore=False)` and never calls `update()`.
Running the application does not train the policy. If `policy_loaded` is
false, the behavior is deterministic adaptive fallback, not learned RL.

## 18. Complete decision example

Assume $N=5$, $B=2$, $Y_{\min}=5$, $Y_{\mathrm{target}}=15$, $T_s=6$, and
$T_h=15$. After the initial two-source wave:

$$
t_1=7.4,\quad Y_1=8,\quad M_1=3,\quad
E_1=0,\quad A_1^{\mathrm{active}}=0.
$$

The bucket is `t2|e2|r3|f0|a0`. Without learned values,

$$
t_1\ge T_s\land Y_1\ge Y_{\min},
$$

so the fallback stops. If a loaded table instead contains

$$
Q(S_1,\texttt{launch\_next})=3.7,\qquad
Q(S_1,\texttt{stop\_launching})=1.4,
$$

the greedy learned policy launches another wave of

$$
L_1=\min(2,3)=2
$$

sources because the hard-deadline override is not yet active.

## 19. Mathematical conclusion

The implemented system is a finite, wave-level, tabular Q-learning controller:

$$
\text{bucketed state}
+\text{two actions}
+\text{linear reward}
+\text{offline TD learning}
+\text{greedy inference}.
$$

It optimizes a discounted proxy for verified yield, latency, source use, and
failure. It does not directly optimize ranking metrics, learn during live
searches, select named sources, or guarantee convergence. Those distinctions
are part of the mathematics of the system.
