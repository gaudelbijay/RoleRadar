# Mathematics of semantic job retrieval

[Documentation index](document.md)

This document explains the mathematics planned for local semantic embeddings,
cosine retrieval, BM25, Reciprocal Rank Fusion, and optional CrossEncoder
reranking. It is a design reference. Semantic ranking is not connected to the
live application yet.

## 1. Retrieval problem

Let $q$ be a search query and let:

$$
D=\{d_1,d_2,\ldots,d_n\}
$$

be the eligible job documents. We want a relevance function:

$$
s(q,d_i)
$$

that assigns a higher value to a job whose meaning is more closely related to
the query.

A semantic embedding model defines a function:

$$
f:\text{text}\rightarrow\mathbb{R}^{m}
$$

where $m$ is the embedding dimension. The same model encodes the query and
every document:

$$
\mathbf{q}=f(q), \qquad \mathbf{d}_i=f(d_i)
$$

For a 384-dimensional model:

$$
\mathbf{q},\mathbf{d}_i\in\mathbb{R}^{384}
$$

Individual coordinates do not normally correspond to human-readable labels.
Meaning is distributed across the complete vector.

## 2. Tokenization

The model cannot process raw text directly. A tokenizer divides text into
tokens and maps them to vocabulary IDs:

$$
[t_1,t_2,\ldots,t_L]
$$

where $L$ is sequence length. A phrase such as `robotics manipulation
engineer` might be represented conceptually as:

```text
[CLS], robot, ##ics, manipulation, engineer, [SEP]
```

The exact segmentation depends on the selected model.

## 3. Token embeddings

Let:

$$
E\in\mathbb{R}^{V\times h}
$$

be a learned embedding matrix, where $V$ is vocabulary size and $h$ is the
transformer hidden dimension. Token $t_i$ selects row:

$$
\mathbf{e}_i=E[t_i]
$$

The sequence becomes:

$$
X=
\begin{bmatrix}
\mathbf{e}_1^\top\\
\mathbf{e}_2^\top\\
\vdots\\
\mathbf{e}_L^\top
\end{bmatrix}
\in\mathbb{R}^{L\times h}
$$

Position information is added because attention alone does not encode order:

$$
\mathbf{x}_i=\mathbf{e}_i+\mathbf{p}_i
$$

where $\mathbf{p}_i$ is a positional representation.

## 4. Self-attention

Given $X$, one attention head computes:

$$
Q=XW_Q,\qquad K=XW_K,\qquad V=XW_V
$$

The unnormalized attention matrix is:

$$
A_{\text{raw}}=\frac{QK^\top}{\sqrt{d_k}}
$$

where $d_k$ is the key dimension. Softmax converts each row into weights:

$$
A_{ij}=
\frac{\exp(A_{\text{raw},ij})}
{\sum_{r=1}^{L}\exp(A_{\text{raw},ir})}
$$

Every row satisfies:

$$
\sum_j A_{ij}=1
$$

The contextual output is:

$$
Z=AV
$$

Thus each token becomes a weighted combination of information from other
tokens.

### Attention masks

Padding tokens must not contribute. Given a mask $m_j\in\{0,1\}$, blocked
positions receive a very negative logit before softmax:

$$
B_{ij}=
\begin{cases}
0,&m_j=1\\
-\infty,&m_j=0
\end{cases}
$$

$$
A=\operatorname{softmax}(A_{\text{raw}}+B)
$$

### Multi-head attention

For head $r$:

$$
Z_r=
\operatorname{softmax}
\left(
\frac{Q_rK_r^\top}{\sqrt{d_k}}
\right)V_r
$$

The heads are concatenated and projected:

$$
Z_{\text{multi}}
=
\operatorname{Concat}(Z_1,\ldots,Z_H)W_O
$$

Multiple heads give the model capacity to represent different contextual
relationships.

## 5. Feed-forward layers and normalization

Each token passes through a position-wise feed-forward network:

$$
\operatorname{FFN}(\mathbf{x})
=
W_2\sigma(W_1\mathbf{x}+\mathbf{b}_1)+\mathbf{b}_2
$$

A common activation is GELU:

$$
\operatorname{GELU}(x)
\approx
\frac{x}{2}
\left(
1+\tanh
\left[
\sqrt{\frac{2}{\pi}}
\left(x+0.044715x^3\right)
\right]
\right)
$$

Residual connections preserve the input signal:

$$
Y=X+\operatorname{Attention}(X)
$$

$$
H=Y+\operatorname{FFN}(Y)
$$

For a hidden vector $\mathbf{x}$, layer normalization uses:

$$
\mu=\frac{1}{h}\sum_{i=1}^{h}x_i
$$

$$
\sigma^2=\frac{1}{h}\sum_{i=1}^{h}(x_i-\mu)^2
$$

$$
\operatorname{LayerNorm}(\mathbf{x})
=
\gamma\odot
\frac{\mathbf{x}-\mu}{\sqrt{\sigma^2+\epsilon}}
+\beta
$$

After all transformer blocks, the model returns contextual token vectors:

$$
H\in\mathbb{R}^{L\times h}
$$

## 6. Pooling

Retrieval requires one vector for the entire text rather than one per token.

### Masked mean pooling

$$
\mathbf{s}
=
\frac{\sum_{i=1}^{L}m_i\mathbf{h}_i}
{\sum_{i=1}^{L}m_i}
$$

where $m_i=0$ for padding tokens.

### CLS pooling

Some models instead use:

$$
\mathbf{s}=\mathbf{h}_{\mathrm{CLS}}
$$

The chosen Sentence Transformers model determines the correct pooling strategy.
The application must use the model's configured pooling rather than inventing a
different one.

A projection layer may map hidden dimension $h$ to final embedding dimension
$m$:

$$
\mathbf{z}=W_P\mathbf{s}+\mathbf{b}_P
$$

## 7. L2 normalization

For vector $\mathbf{z}$:

$$
\|\mathbf{z}\|_2
=
\sqrt{\sum_{j=1}^{m}z_j^2}
$$

The unit-normalized vector is:

$$
\hat{\mathbf{z}}
=
\frac{\mathbf{z}}{\|\mathbf{z}\|_2}
$$

and:

$$
\|\hat{\mathbf{z}}\|_2=1
$$

For example:

$$
\mathbf{z}=
\begin{bmatrix}
3\\4
\end{bmatrix},
\qquad
\|\mathbf{z}\|_2=5
$$

$$
\hat{\mathbf{z}}=
\begin{bmatrix}
0.6\\0.8
\end{bmatrix}
$$

## 8. Dot product and cosine similarity

The dot product is:

$$
\mathbf{a}\cdot\mathbf{b}
=
\sum_{j=1}^{m}a_jb_j
$$

Cosine similarity is:

$$
\operatorname{cos}(\mathbf{a},\mathbf{b})
=
\frac{\mathbf{a}\cdot\mathbf{b}}
{\|\mathbf{a}\|_2\|\mathbf{b}\|_2}
$$

It measures vector direction:

$$
\cos(0^\circ)=1,\qquad
\cos(90^\circ)=0,\qquad
\cos(180^\circ)=-1
$$

When both vectors are unit normalized:

$$
\operatorname{cos}(\hat{\mathbf{a}},\hat{\mathbf{b}})
=
\hat{\mathbf{a}}^\top\hat{\mathbf{b}}
$$

### Numerical example

Let:

$$
\mathbf{q}=
\begin{bmatrix}
0.8\\0.6
\end{bmatrix}
$$

and:

$$
\mathbf{d}_A=
\begin{bmatrix}
0.75\\0.6614
\end{bmatrix}
$$

Then:

$$
s_A
=
0.8(0.75)+0.6(0.6614)
\approx0.99684
$$

For:

$$
\mathbf{d}_B=
\begin{bmatrix}
-0.6\\0.8
\end{bmatrix}
$$

$$
s_B=0.8(-0.6)+0.6(0.8)=0
$$

Therefore document $A$ ranks above document $B$.

Cosine similarity is not a probability. A value of $0.84$ does not mean an
84% probability of relevance.

## 9. Batch similarity

Stack normalized document embeddings as rows:

$$
D=
\begin{bmatrix}
\hat{\mathbf{d}}_1^\top\\
\hat{\mathbf{d}}_2^\top\\
\vdots\\
\hat{\mathbf{d}}_n^\top
\end{bmatrix}
\in\mathbb{R}^{n\times m}
$$

All query-document similarities are computed simultaneously:

$$
\mathbf{s}=D\hat{\mathbf{q}}
$$

where:

$$
\mathbf{s}\in\mathbb{R}^{n}
$$

and:

$$
s_i=\hat{\mathbf{d}}_i^\top\hat{\mathbf{q}}
$$

For a few hundred jobs, this matrix multiplication is inexpensive. The costly
operation is transformer encoding, which is why a vector database is not
initially necessary.

## 10. Computational complexity

Transformer self-attention contains a term approximately proportional to:

$$
O(L^2h)
$$

because every token attends to every token. This motivates removing boilerplate
and limiting document length.

After encoding, brute-force cosine comparison costs:

$$
O(nm)
$$

For $n=300$ and $m=384$:

$$
nm=115{,}200
$$

multiply-add comparisons, which is small for local numerical libraries.

## 11. Ranking and numerical safety

Given scores:

$$
\mathbf{s}=[s_1,\ldots,s_n]
$$

descending order is:

$$
\pi=\operatorname{argsort}(-\mathbf{s})
$$

with:

$$
s_{\pi_1}\geq s_{\pi_2}\geq\cdots\geq s_{\pi_n}
$$

Ties should use the document ID as a deterministic secondary key.

Scores must be finite:

$$
\operatorname{isfinite}(s_i)=\text{True}
$$

NaN and positive or negative infinity must be rejected.

Cosine similarity is undefined for a zero vector because:

$$
\|\mathbf{0}\|_2=0
$$

The implementation must reject vectors whose norm is below a small tolerance
$\epsilon$.

Floating-point tests use a tolerance rather than exact equality:

```python
assert score == pytest.approx(expected, abs=1e-6)
```

## 12. Score calibration

An uncalibrated cosine score is geometric similarity, not probability. Turning
it into a probability requires labeled examples and a calibration model such
as:

$$
P(y=1\mid s)
=
\frac{1}{1+\exp[-(as+b)]}
$$

Until such calibration exists, the application should use rank order and label
the value as semantic similarity.

A fixed threshold such as $s\geq0.70$ must not be assumed valid across models.
Thresholds require measured relevant and irrelevant score distributions.

## 13. Bi-encoder retrieval

The planned embedding system is a bi-encoder:

$$
\mathbf{q}=f(q),\qquad \mathbf{d}_i=f(d_i)
$$

$$
s_i=\mathbf{q}^\top\mathbf{d}_i
$$

Documents can be encoded once and cached. The query is encoded once per search.
This is efficient, but query and document tokens do not directly interact.

Some models use symmetric input. Others require prefixes:

$$
\mathbf{q}=f(\text{`query: '}+q)
$$

$$
\mathbf{d}=f(\text{`passage: '}+d)
$$

Prefixes must follow the chosen model's training configuration.

## 14. Contrastive training intuition

Given query $q_i$, relevant document $d_i^+$, and negatives $d_{ij}^-$, a
contrastive objective can be written:

$$
\mathcal{L}_i
=
-\log
\frac{\exp(s(q_i,d_i^+)/\tau)}
{\exp(s(q_i,d_i^+)/\tau)+
\sum_j\exp(s(q_i,d_{ij}^-)/\tau)}
$$

where $\tau$ is temperature. The objective increases positive-pair
similarity and decreases negative-pair similarity. We plan to use a pretrained
model, not train this objective inside the application.

## 15. CrossEncoder reranking

A CrossEncoder jointly processes a query-document pair:

```text
[CLS] query [SEP] job text [SEP]
```

The joint transformer representation produces a score:

$$
s_{\text{cross}}
=
W\mathbf{h}_{\mathrm{CLS}}+b
$$

It can model fine-grained token interactions but must run separately for every
pair. Therefore:

$$
\text{bi-encoder retrieval}
\rightarrow
\text{top 30--50 candidates}
\rightarrow
\text{CrossEncoder reranking}
$$

is appropriate, while CrossEncoding every fetched listing is unnecessarily
expensive.

## 16. BM25

BM25 complements semantic retrieval with exact lexical evidence:

$$
\operatorname{BM25}(q,d)
=
\sum_{t\in q}
\operatorname{IDF}(t)
\frac{f(t,d)(k_1+1)}
{f(t,d)+k_1
\left(
1-b+b\frac{|d|}{\operatorname{avgdl}}
\right)}
$$

where:

- $f(t,d)$ is the frequency of term $t$ in document $d$;
- $|d|$ is document length;
- $\operatorname{avgdl}$ is average document length;
- $k_1$ controls term-frequency saturation;
- $b$ controls document-length normalization.

One inverse-document-frequency form is:

$$
\operatorname{IDF}(t)
=
\log
\left(
\frac{N-n_t+0.5}{n_t+0.5}+1
\right)
$$

where $N$ is corpus size and $n_t$ is the number of documents containing
term $t$.

BM25 is valuable for exact terms such as `ROS 2`, professional credentials,
degree names, and specialized technologies.

## 17. Reciprocal Rank Fusion

BM25 and cosine scores have incompatible scales. RRF combines their positions:

$$
\operatorname{RRF}(d)
=
\sum_{r\in R}
\frac{1}{k+\operatorname{rank}_r(d)}
$$

where $R$ is the collection of ranking systems.

For $k=60$, document $A$ at BM25 rank 1 and semantic rank 5 receives:

$$
\operatorname{RRF}(A)
=
\frac{1}{61}+\frac{1}{65}
\approx0.03177
$$

Document $B$ at BM25 rank 8 and semantic rank 1 receives:

$$
\operatorname{RRF}(B)
=
\frac{1}{68}+\frac{1}{61}
\approx0.03110
$$

RRF rewards documents that rank well in multiple systems without pretending
their raw scores are directly comparable.

## 18. Resume evidence

Let:

$$
\mathbf{r}=f(\text{derived resume evidence})
$$

and:

$$
\mathbf{d}=f(\text{job document})
$$

Separate similarities are more interpretable than blindly averaging vectors:

$$
s_q=\cos(\mathbf{q},\mathbf{d})
$$

$$
s_r=\cos(\mathbf{r},\mathbf{d})
$$

A future measured combination could be:

$$
s_{\text{semantic}}
=
\alpha s_q+(1-\alpha)s_r
$$

with $0\leq\alpha\leq1$, but weights must be selected through evaluation.
Initially, separate rank lists combined through RRF are safer.

Only derived professional evidence should be embedded. Raw contact details and
full resume text should not be persisted by default.

## 19. Evaluation mathematics

### Precision at $k$

$$
P@k
=
\frac{1}{k}
\sum_{i=1}^{k}\operatorname{rel}_i
$$

where $\operatorname{rel}_i\in\{0,1\}$.

### Recall at $k$

$$
\operatorname{Recall}@k
=
\frac{|\text{relevant documents in top }k|}
{|\text{all relevant documents}|}
$$

### Discounted cumulative gain

$$
DCG@k
=
\sum_{i=1}^{k}
\frac{2^{\operatorname{rel}_i}-1}
{\log_2(i+1)}
$$

### Normalized DCG

$$
NDCG@k=\frac{DCG@k}{IDCG@k}
$$

where $IDCG$ is the score for the ideal ordering.

The benchmark must include hard negatives such as marketing, sales, and
recruiting roles at robotics companies.

## 20. Complete planned ranking definition

First define deterministic eligibility:

$$
g(d_i)
=
g_{\text{country}}(d_i)
g_{\text{date}}(d_i)
g_{\text{age}}(d_i)
g_{\text{search-type}}(d_i)
g_{\text{safety}}(d_i)
$$

Every factor is binary. If any factor is zero:

$$
g(d_i)=0
$$

and the job is excluded before model work.

For eligible jobs:

$$
x_i=T(d_i)
$$

where $T$ constructs controlled role-focused text.

$$
\mathbf{q}=f(q),\qquad\mathbf{d}_i=f(x_i)
$$

$$
\hat{\mathbf{q}}
=
\frac{\mathbf{q}}{\|\mathbf{q}\|_2},
\qquad
\hat{\mathbf{d}}_i
=
\frac{\mathbf{d}_i}{\|\mathbf{d}_i\|_2}
$$

$$
s_i^{\text{semantic}}
=
\hat{\mathbf{q}}^\top\hat{\mathbf{d}}_i
$$

After calculating semantic and BM25 ranks:

$$
s_i^{\text{RRF}}
=
\frac{1}{k+r_i^{\text{semantic}}}
+
\frac{1}{k+r_i^{\text{BM25}}}
$$

The fused top candidates may receive a CrossEncoder score. Resume fit, optional
city preference, and recency are later explainable adjustments. No semantic or
neural score may bypass mandatory gates.

## 21. Mathematical implementation sequence

1. Define immutable document and result contracts.
2. Build controlled semantic job text.
3. Add a lazy local bi-encoder adapter.
4. Validate vector dimensions and finite values.
5. L2-normalize query and document vectors.
6. Compute batched cosine similarity through matrix multiplication.
7. Add deterministic ranking and tie-breaking.
8. Add content-hash caching.
9. Establish an offline relevance benchmark.
10. Add BM25 and RRF only after individual behavior is measured.
11. Evaluate a CrossEncoder on the fused top candidates.
12. Connect the pipeline in shadow mode before changing visible results.

The live application must remain functional through deterministic ranking when
any optional semantic component is unavailable.
