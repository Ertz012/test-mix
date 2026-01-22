# The Traffic Analysis of Continuous-Time Mixes

**George Danezis**
University of Cambridge, Computer Laboratory,
15 JJ Thomson Avenue, Cambridge CB3 0FD, United Kingdom.
`George.Danezis@cl.cam.ac.uk`

**Abstract.** We apply the information-theoretic anonymity metrics to continuous-time mixes, that individually delay messages instead of batching them. The anonymity of such mixes is measured based on their delay characteristics, and as an example the exponential mix (sg-mix) is analysed, simulated and shown to use the optimal strategy. We also describe a practical and powerful traffic analysis attack against connection based continuous-time mix networks, despite the presence of some cover traffic. Assuming a passive observer, the conditions are calculated that make tracing messages through the network possible.

## 1 Introduction

Building blocks for anonymous communication operating by batching input messages in rounds, such as threshold or pool mixes, have recently been the subject of extensive study [15, 16, 6, 17]. The same is not true for mixes that operate in continuous-time, by individually delaying messages. An example of these is the sg-mix construction presented by Kesdogan et al [10]. Its inventors present an analysis of its anonymity, but this cannot easily be generalised to other mix strategies.

We will present a new framework for analysing the anonymity provided by mix strategies that individually delay messages. In order to make the analysis easier, we assume that the rate of arrival of messages to the mixes is Poisson distributed. Using the work presented here, different mix strategies can be analysed but we choose to illustrate our method with an analysis of the exponential mix (sg-mix), both because it is relatively simple and because it has been extensively mentioned in the literature. Furthermore, a section is devoted to showing that given some latency constraints the exponential mix is the mixing strategy providing maximal anonymity.

We then present a powerful attack that given enough packets, can break the anonymity provided by connection-based mix networks functioning in continuous-time. The attack relies on detecting an input traffic pattern, at the outputs of the mixes or network, using signal detection techniques. A detailed description is given on how to perform this attack, and confidence intervals are provided to assess the reliability of the results. The attack can be used effectively against many proposed anonymous communications systems such as Onion Routing [13], Freedom [4], TARZAN [7] or MorphMix [14].

## 2 Delay characteristic and anonymity

The main aim of a mix, as introduced by Chaum [5], is to hide the correspondence between the input and output messages it relays. First it makes its inputs and outputs bitwise unlinkable, which means that a third party cannot link them by observing their bit patterns without knowledge of the cryptographic keys used to perform the transform. Secondly it blurs the timing correlations between inputs and outputs by batching, introducing appropriate random delays and reordering messages. Continuous-time mixes achieve this by delaying each message individually and independently of the others.

We can say that a particular mix strategy is described by its delay characteristic. This is a function $f(\beta|\alpha)$ that represents the probability a message injected in the mix at time $\alpha$ leaves the mix at time $\beta$, where $\alpha \le \beta$. Since $f(\beta|\alpha)$ is a conditional probability distribution, it is normalised.

$$\forall\alpha.\int_{\alpha}^{+\infty}f(\beta|\alpha)d\beta=1 \quad (1)$$

The inverse delay characteristic, $f^{\prime}(\alpha|\beta)$, of the same mix strategy is a probability distribution that describes the likelihood a message being ejected at time $\beta$ was injected at time $\alpha$. Again because it is a conditional probability distribution it is normalised.

$$\forall\beta.\int_{-\infty}^{\beta}f^{\prime}(\alpha|\beta)d\alpha=1 \quad (2)$$

The two characteristics are related, since the second $f^{\prime}$ can be calculated using Bayes theorem from $f$. Some knowledge of the probability of arrivals at particular times is necessary to perform this conversion. To simplify things, we will consider that arrivals are Poisson distributed with a rate $\lambda_{\alpha}$. In a Poisson process, the probability of an arrival is independent from other arrivals or the time $\alpha$.

$$f^{\prime}(\alpha|\beta)=\frac{f(\beta|\alpha)Pr[Arrival~at~\alpha]}{\int_{-\infty}^{\beta}f(\beta|\alpha)Pr[Arrival~at~\alpha]d\alpha} = \frac{f(\beta|\alpha)}{\int_{-\infty}^{\beta}f(\beta|\alpha)d\alpha} \quad (3)(4)$$

Therefore, given the delay characteristics and some assumptions about the traffic in the network we can calculate the inverse delay characteristic. These will allow us to measure the effective sender and receiver anonymity for this mix strategy.

We will use the metric introduced in [15] to calculate the sender anonymity provided by a mixing strategy. This metric is based on defining a random variable that describes the possible senders of a message and calculating the entropy of its underlying probability distribution. The entropy is then a measure of the anonymity provided, and can be interpreted as the amount of information an attacker is missing to deterministically link the messages to a sender.

We assume that in a time interval $(\beta-T, \beta)$, $K$ messages arrive at the mix, where $K$ is distributed according to a Poisson distribution with parameter $\lambda_{\alpha}$. These messages arrive at times $X_{1...K}$ each distributed according to a uniform distribution $U(t)$ over the time interval of length $T$ (as required by the Poisson distribution). Given the inverse delay characteristic of the mix $f^{\prime}(\alpha|\beta)$, the sender anonymity $\mathcal{A}$ provided by the mix can be calculated. It represents the entropy of the probability distribution describing how likely each of the inputs $X_{i}$ is to be output at a particular time $\beta$.

$$\mathcal{A}=\sum_{i=1}^{K}\frac{f^{\prime}(X_{i}|\beta)}{\sum_{j=1}^{K}f^{\prime}(X_{j}|\beta)}log\frac{f^{\prime}(X_{i}|\beta)}{\sum_{j=1}^{K}f^{\prime}(X_{j}|\beta)} \quad (5)$$

$$=\frac{1}{\sum_{j=1}^{K}f^{\prime}(X_{j}|\beta)}(\sum_{i=1}^{K}f^{\prime}(X_{i}|\beta)log~f^{\prime}(X_{i}|\beta))-log\sum_{j=1}^{K}f^{\prime}(X_{j}|\beta) \quad (6)$$

From the Law of Large Numbers¹ we know that the sums converge to:

$$\sum_{j=1}^{K}f^{\prime}(X_{j}|\beta)\rightarrow\frac{K}{T}\rightarrow\lambda_{\alpha} \quad (7)$$

$$\sum_{i=1}^{K}f^{\prime}(X_{i}|\beta)log~f^{\prime}(X_{i}|\beta)\rightarrow\frac{K}{T}\int_{\beta-T}^{\beta}f^{\prime}(t|\beta)log~f^{\prime}(t|\beta)dt\rightarrow\lambda_{\alpha}\mathcal{E}[f^{\prime}(\alpha|\beta)] \quad (8)$$

Thus the fraction $K/T$ converges to $\lambda_{\alpha}$, which is the rate of arrival of messages to the mix and the integral (8) reduces to the entropy of the inverse delay characteristic function $\mathcal{E}[f^{\prime}(\alpha|\beta)]$. Therefore the sender anonymity of a continuous mix with delay characteristic $f^{\prime}$ and a rate of arrival $\lambda_{\alpha}$ can be expressed.

$$\mathcal{A}\rightarrow\mathcal{E}[f^{\prime}(\alpha|\beta)]-log~\lambda_{\alpha} \quad (9)$$

Putting this into words, the effective sender anonymity set size of the mixing strategy will converge towards the relative entropy of the inverse delay characteristic, as defined by Shannon [19], minus the logarithm of the rate at which messages are received. Similarly the recipient anonymity set size can be calculated using the same techniques and the delay characteristic of the mix strategy.

---
¹ For large K and T, $\lim_{K\rightarrow\infty}\sum_{j=1}^{K}f^{\prime}(X_{j}|\beta)=K\int_{\beta-T}^{\beta}U(t)f^{\prime}(t|\beta)dt\rightarrow\frac{K}{T}$. Note that for the approximation we do not assume the rate to be large, but simply the observation period T to be large enough to observe some traffic.

### 2.1 The exponential mix

In order to illustrate the calculations above we analyse the exponential mix. The exponential mix has been presented as a mixing strategy by Kesdogan et al [10]. In their design additional features are implemented to avoid $(n-1)$ attacks [8, 16], that we are not concerned with in this work.

The exponential mix can be abstracted as an $M/M/\infty$ queue. We assume, as required from the calculations above, the arrival rates of messages to be Poisson distributed with rate $\lambda_{\alpha}$. Each of the messages that arrives at the mix is delayed according to a random variable that follows the exponential distribution with parameter $\mu$. Therefore the delay characteristic of the exponential mix is:

$$f(\beta|\alpha)=\mu e^{-\mu(\beta-\alpha)} \quad (10)$$

From equation (4) we can calculate the inverse delay characteristic $f^{\prime}$. Due to the nature of the exponential distribution, it is equal to the delay characteristic $f$.

$$f^{\prime}(\alpha|\beta)=\frac{f(\beta|\alpha)}{\int_{-\infty}^{\beta}f(\beta|\alpha)d\alpha}=f(\beta|\alpha)=\mu e^{-\mu(\beta-\alpha)} \quad (11)$$

Using the inverse delay characteristic, and (9) we can now calculate the expected sender anonymity ($\mathcal{E}[\cdot]$ is the entropy function).

$$\mathcal{A}=\mathcal{E}[Pr[\alpha]]\rightarrow\mathcal{E}[f^{\prime}(\alpha|\beta)]-log~\lambda_{\alpha} \quad (12)$$

$$=\int_{-\infty}^{\beta}\mu e^{-\mu(\beta-\alpha)}log~\mu e^{-\mu(\beta-\alpha)}d\alpha-log~\lambda_{\alpha}=-log\frac{\lambda_{\alpha}e}{\mu} \quad (13)$$

To check the above result (since it relies on the approximations (7) and (8)) a simulation was run for some values of $\lambda_{\alpha}$ and $\mu$, and the results were compared with the metric predictions in equation (13). The inverse delay characteristic was used to calculate the probability assigned to a number of messages arriving at a mix. The number of messages was Poisson distributed according to $\lambda_{\alpha}$, and their time of arrival was chosen uniformly. Their delay was a random variable distributed according to the exponential distribution with rate $\mu$. The absolute difference between the predictions (figure 1(a)) and the simulation (figure 1(b)) is shown in figure 1(c).

The main divergence of the simulated results from the predicted results, is in the region where the metric predicts positive values for the entropy. This is intuitively impossible and indeed is the largest error from the actual simulation results. The conditions for which the model, that the equation (13) describes, should not be considered accurate is described by:

$$-log\frac{\lambda_{\alpha}e}{\mu}>0\Rightarrow\mu>\lambda_{\alpha}e \quad (14)$$

It is clear that an $M/M/\infty$ queue with a departure rate $\mu$ larger than the arrival rate $\lambda_{\alpha}$ would not provide much anonymity most of the time. The average time a message would spend in the mix is $\frac{1}{\mu}$ while the average time between message arrivals is $\frac{1}{\lambda_{\alpha}}$ which is larger. Therefore the mix would behave on average as a first-in first-out queue.

### 2.2 The latency of a mix strategy

The delay characteristic of a mix can also be used to calculate the latency introduced by a mix strategy and its variance. This can be done trivially since the latency of the mix strategy is the expectation $E[\cdot]$ of the delay characteristic function $f(\beta|\alpha)$.

$$E[f(\beta|\alpha)]=\int_{\alpha}^{+\infty}(\beta-\alpha)f(\beta|\alpha)d\beta \quad (15)$$

Similarly the variance $V[\cdot]$ of the delay can be calculated using the expectation:

$$V[f(\beta|\alpha)]=\int_{\alpha}^{+\infty}(E[f(\beta|\alpha)]-(\beta-\alpha))^{2}f(\beta|\alpha)d\beta \quad (16)$$

For the exponential mix the mean delay is $\frac{1}{\mu}$ and its variance is $\frac{1}{\mu^{2}}$.

### 2.3 Optimal mixing strategies

So far, we have described how to measure the anonymity and latency of a continuous-time mix, given its delay strategy. Naturally, the next problem is finding a mix strategy that maximises entropy, and therefore anonymity. We need to find a distribution $f$ with a particular mean $a$, which represents the average latency of the mix. Since a packet can only leave the mix after it arrived, the function $f$ can only occupy half the timeline, namely the interval $[0, +\infty)$. We prove that the optimal probability distribution $f$ is the exponential probability distribution. This result was first proved by Shannon [19] using techniques from the calculus of variations [22]. We want to minimise:

$$E[f(x)]=-\int_{0}^{-\infty}f(x)log~f(x)dx \quad (17)$$

Subject to the constraints:

$$a=\int_{0}^{-\infty}xf(x)dx \quad (18)$$

and

$$\int_{0}^{-\infty}f(x)dx=1 \quad (19)$$

Then by the calculus of variations [22] we must solve:

$$\frac{\partial(-f(x)log~f(x)+\lambda xf(x)+\mu f(x))}{\partial f}=0 \quad (20)$$

$$\Rightarrow-1-log~f(x)+\lambda x+\mu=0 \quad (21)$$

$$\Rightarrow f(x)=e^{\lambda x+\mu-1} \quad (22)$$

After incorporating the constraints, the resulting function is:

$$f(x)=\frac{1}{a}e^{-\frac{1}{a}x}$$

This is exactly the exponential mix as analysed in section 2.1, which is therefore optimal.

## 3 Traffic analysis of continuous mixes

In the previous sections we have considered the anonymity of single packets mixed using a continuous-time mixing strategy. Continuous-time mixes can approximate circuit-based systems that implement minimal mixing, in order to provide real-time communications. In such systems a number of packets, all belonging to the same stream, are quickly routed through the same path in the network.

The Onion Routing project [20] first drew the community’s attention to the need for traffic padding to protect against fine-grained traffic analysis. Since then some publications have discussed traffic analysis and possible defences against it [1, 12]. Others refer to the same problem in the context of intersection attacks [3, 2, 9] and present padding as a potential protection. Some previous work has drawn attention to the vulnerabilities of anonymous systems to "timing" attacks [14], while Kesdogan et al [9] present a concrete attack. Serjantov et al [18] present a traffic analysis attack based on counting packets on the links, while Levine et al [11] uses more fine grained traffic patterns to trace them. We will now present a very general way of performing traffic analysis on streams of packets travelling through the same route in a continuous-time mix network. We show that after a certain number of messages, that can be calculated, the communication can be traced with high confidence.

### 3.1 Concrete traffic analysis techniques

We denote as $f(t)$ the function that describes the traffic, to be traced, feeding into a continuous mix with delay characteristic $d(x)$. We assume that all messages described by $f(t)$ belong to the same stream, and will therefore be ejected on the same output link. We will assume that there are two output links. The attacker’s aim is to determine on which output link the stream is redirected.

On the first link we observe messages coming out at times $X_{1\cdot\cdot\cdot n}$ and on the second link messages come out at times $Y_{1\cdot\cdot\cdot m}$ in the time interval $[0, T]$. $H_{0}$ represents the hypothesis the input stream $f(t)$ is interleaved in the first channel described by the observations $X_{i}$, and $H_{1}$ that is in the second corresponding with $Y_{i}$.

In order to detect the streams we will make some approximations. We will create two model probability distributions $C_{X}$ and $C_{Y}$ and will assume that all messages in the output channels are independent samples out of one of these distributions. The difference between $C_{X}$ and $C_{Y}$ is due to our attempt to model the noise in the two output channels. We will also consider that all the other messages are uniformly distributed in the interval $t\in[0,T]$ according to the distribution $U(t)=u.$

When $H_{0}$ is true the stream under observation is interleaved in the observations $X_{i}$. We will model each of them as following the probability distribution:

$$C_{X}(t)=\frac{\lambda_{f}(d*f)(t)+(\lambda_{X}-\lambda_{f})U(t)}{\lambda_{X}} \quad (23)$$

The probability distribution $(d*f)(t)$ is the convolution of the input signal with the delay characteristic of the mix. The probability a message delayed by $d(x)$ is output at time $t$ given an input stream of messages described by $f(t)$ is described by this convolution.

$$(d*f)(t)=\int d(x)f(t-x)dx \quad (24)$$

Furthermore $\lambda_{f}$ is the rate of messages in the input signal, while $\lambda_{X}$ is the rate of the output channel. Finally $U(t)=u$ is the uniform distribution in the interval $[0, T]$.

Similarly if hypothesis $H_{1}$ is true, the signal is interleaved in the observations $Y_{i}$ that follow the distribution:

$$C_{Y}(t)=\frac{\lambda_{f}(d*f)(t)+(\lambda_{Y}-\lambda_{f})U(t)}{\lambda_{Y}} \quad (25)$$

In order to decide which of the two hypothesis is valid, $H_{0}$ or $H_{1}$, we can calculate the likelihood ratio of the two alternative hypothesis.

$$\frac{\mathcal{L}(H_{0}|X_{i},Y_{j})}{\mathcal{L}(H_{1}|X_{i},Y_{j})}=\frac{\prod_{i=1}^{n}C_{X}(X_{i})\prod_{j=1}^{m}u}{\prod_{i=1}^{n}u\prod_{j=1}^{m}C_{Y}(Y_{j})}>1 \quad (26)$$

We choose to accept hypothesis $H_{0}$ if condition (26) is true, and hypothesis $H_{1}$ otherwise. Section 3.3 will show how we calculate our degree of confidence when making this choice.

### 3.2 A simple example

Figure 2 shows six diagrams illustrating the traffic analysis attack. The first column represents, from top to bottom, the signal that we inject in a mix and the two output channels, one of which contains the delayed signal. The right hand side column represents the delay characteristic of the network, an exponential distribution in this case (sg-mix), the "model" that is created by convolving the input signal with the delay characteristic and, at the bottom, the log-likelihood ratio.

The cover traffic or "noise" in the above experiments is assumed to be a Poisson process. Noise is added both to the channel that contains the stream under surveillance (in this case link 1, $X_{i}$) and the other link $(Y_{i})$. The rate of the signal $f(t)$ in the traffic analysis graphs shown above is 50 messages, while the noise added in $X_{i}$ has a rate of 150 messages. The second link contains random padding with a rate of 200 messages (Y). The delay characteristic $d(x)$ chosen to illustrate the traffic analysis technique is exponential with a departure rate of 30. The graphs therefore illustrate the traffic analysis of a sg-mix node. The decision graph presents the logarithm of the likelihood ratio $\log \frac{\mathcal{L}(H_{0}|X_{i},Y_{j})}{\mathcal{L}(H_{1}|X_{i},Y_{j})}$ as an attacker would compute it at each point in the simulation time. After 700 simulation ticks the log-likelihood ratio is clearly positive indicating that $H_{0}$ should be accepted.

### 3.3 Performance of the traffic analysis attack

There are two questions that need to be answered concerning the traffic analysis attack presented. First the conditions under which it is at all possible must be established. Second the number of observations necessary to get reliable results has to be calculated.

By simple mathematical manipulations with logarithms, we can derive that the likelihood ratio test, applied to select the most appropriate hypothesis can be expressed using sums of random variables:

$$\mathcal{L}_{H_{0}/H_{1}}=\frac{\mathcal{L}(H_{0}|X_{i},Y_{j})}{\mathcal{L}(H_{1}|X_{i},Y_{j})}=\frac{\prod_{i=1}^{n}C_{X}(X_{i})\prod_{j=1}^{m}u}{\prod_{i=1}^{n}u\prod_{j=1}^{m}C_{Y}(Y_{j})}>1 \quad (27)$$

$$\Rightarrow log\mathcal{L}_{H_{0}/H_{1}}=\sum_{i=1}^{n}log~C_{X}(X_{i})-\sum_{j=1}^{m}log~C_{Y}(Y_{j})+(m-n)log~u>0 \quad (28)$$

The expression above is equivalent to (26) the rule by which we choose the hypothesis to accept. The condition for which the attack is possible is that the decision rule (28) must not equal zero. This could be the case if both $C_{X}$ and $C_{Y}$ were uniform distributions. Even through the inequality might hold it does not give us any measure of confidence in the result. We will therefore attempt to find bounds within which we are confident that the decision is correct.

Note that the two sums will converge to the expectations $nE[log~C_{X}(X)|X_{i}\sim X]$ and $mE[log~C_{Y}(Y)|Y_{j}\sim Y]$. The notation $X_{i}\sim X$ means that the samples $X_{i}$ are sampled from the distribution X, and the samples $Y_{j}$ from the distribution Y. The two distributions X and Y are different according to which of the two hypothesis is accepted. In case $H_{0}$ then $X_{i}\sim C_{X}$, $Y_{j}\sim U$. Alternatively if $H_{1}$ is true then $X_{i}\sim U$ and $Y_{j}\sim C_{Y}$. Without losing generality we will demonstrate when to accept hypothesis $H_{0}$. The derivations are the same in the other case.

In case the hypothesis $H_{0}$ is correct, $E[log~C_{X}(X)|H_{0}:X_{i}\sim C_{X}]$ converges to the entropy of the probability distribution $C_{X}(t)$ denoted $\mathcal{E}[C_{X}(t)]$, since the probabilities assigned to each value of the random variable $log~C_{X}(X)$ follow the distribution $C_{X}$.

$$E[log~C_{X}(X)|H_{0}:X_{i}\sim C_{X}]=\int_{0}^{T}C_{X}(t)log~C_{X}(t)dt=\mathcal{E}[C_{X}(t)] \quad (29)$$

On the other hand $E[log~C_{Y}(Y)|H_{0}:Y_{j}\sim U]$ converges to the expectation of $C_{Y}$ namely $E[log~C_{Y}(t)]$.

$$E[log~C_{Y}(Y)|H_{0}:Y_{j}\sim U]=\int_{0}^{T}u~log~C_{Y}(t)dt=E[log~C_{Y}(t)] \quad (30)$$

Therefore in case we accept hypothesis $H_{0}$ the expected value of the decision rule $log\mathcal{L}_{H_{0}/H_{1}}$ (28) is $\mu_{H_{0}}$:

$$\mu_{H_{0}}=E[\sum_{i=1}^{n}log~C_{X}(X_{i})-\sum_{j=1}^{m}log~C_{Y}(Y_{j})+(m-n)log~u|H_{0}]$$

$$=nE[log~C_{X}(X)|H_{0}]-mE[log~C_{Y}(Y)|H_{0}]+(m-n)log~u$$

$$=n\mathcal{E}[C_{X}(t)]-mE[log~C_{Y}(t)]+(m-n)log~u \quad (31)$$

The variance can be calculated using the above observations:

$$V[log~C_{X}(X)|H_{0}]=\int_{0}^{T}C_{X}(t)(log~C_{X}(t)-\mathcal{E}[C_{X}(X)])^{2}dt \quad (32)$$

$$V[log~C_{Y}(Y)|H_{0}]=\int_{0}^{T}u(log~C_{Y}(t)-E[log~C_{Y}(Y)])^{2}dt \quad (33)$$

Using these we will calculate the variance $\sigma_{H_{0}}^{2}$ of the decision rule $log\mathcal{L}_{H_{0}/H_{1}}$ (28) which is:

$$\sigma_{H_{0}}^{2}=V[\sum_{i=1}^{n}log~C_{X}(X_{i})-\sum_{j=1}^{m}log~C_{Y}(Y_{j})+(m-n)log~u|H_{0}]$$

$$=nV[log~C_{X}(X)|H_{0}]+mV[log~C_{Y}(Y)|H_{0}] \quad (34)$$

Using Chebyshev's inequality² we can derive the condition necessary in order to accept hypothesis $H_{0}$ with confidence $p$. We require the log-likelihood not to deviate, with probability greater than $p$, from its expected value (the mean) more than its mean (which would invalidate our decision rule (28)).

$$p=Pr[|log\mathcal{L}_{H_{0}/H_{1}}-\mu_{H_{0}}|\ge\mu_{H_{0}}]\le\frac{\sigma_{H_{0}}^{2}}{\mu_{H_{0}}^{2}}\Rightarrow p\le\frac{\sigma_{H_{0}}^{2}}{\mu_{H_{0}}^{2}} \quad (35)$$

An equivalent test can be derived to assess our confidence when accepting hypothesis $H_{1}$.

---
² If a random variable has a finite mean and finite variance $\sigma^{2}$, then $\forall k>0$, $Pr[|x-\mu|\ge k]\le\frac{\sigma^{2}}{k^{2}}$

### 3.4 Traffic analysis of networks

We modify slightly the simple techniques described above to perform traffic analysis against a mix network composed of continuous-time mixes. Instead of performing a hypothesis test on two links, we compare all the links in the network with the pattern extracted from the input stream that we want to trace. This way each link is assigned a degree of similarity with the traced input. This can be used to infer some information about the intermediate and final nodes on the path.

To illustrate our techniques we use a mix network made of 50 nodes with 10 links each. The network is sparse, which is consistent with quite a few fielded systems, such as Freedom [4]. Five hundred streams (500) are routed through this network, using a random path of 4 nodes (the same node cannot appear twice in the path). Each stream contains 400 packets during the period the network is under observation, which is 10000 simulation ticks. Mixes delay packets individually using an exponential mix with mean 10 simulation ticks. Figure 3 presents a view of the network, along with the route that the stream under observation takes. The attacker’s objective is to uncover the route of this stream, knowing only its input pattern and entry point, and the traffic on the network links.

As before a pattern (figure 3(b)) is extracted for the input under observation (figure 3(a)) that is compared with each link in the network. The convolution of the input traffic with the exponential delay characteristic, has been used to compute the pattern, but there has been no attempt to model the noise on each channel. The pattern is compared to the traffic on each link of the network. This returns a measure of similarity of the link to the input traced. This in turn can be used to classify the link, as containing the target input on its way to the second mix (hop 1), the third mix (hop 2) or the final mix (hop 3). Alternatively the link might be unrelated to the target input, and simply contain noise. We choose the decision rule in such a way that we avoid false negatives. Figure 4 shows the classification curves that have been compiled after simulations.

The classification of each link as 'noise' or 'candidate link' allows us to simplify the graph of the network. Information can also be extracted relating to how likely the link is to contain the signal traced, and therefore a weighted graph (figure 5(a)) and its corresponding matrix (figure 5(b)) can be extracted. The intensity of the links or the entries in the matrix represents the likelihood a link contains the stream under observation.

A random walk is performed for one to three hops on the resulting graph, starting at the entry point of the observed stream. This provides us with the likely second, third or final nodes of the path (figures 6(a), 6(b) and 6(c) respectively). The stars on the graphs indicate the actual nodes that relay the target stream. In the example shown the final node is not guessed correctly, but is within the three nodes with highest probability. In the presence of longer delays or more traffic the correct nodes might not be the ones with highest likelihood but the attack still yields a lot of information and significantly reduces the effective anonymity provided to the users.

## 4 Further considerations and future work

Measuring anonymity. The work presented measures the average anonymity provided by a mix strategy. One of the important assumptions is that the expected number of messages is received in any time interval $t$, namely $\lambda_{\alpha}t$. The actual number of messages received in any interval may vary according to the Poisson distribution. Should a mix be flooded by the attacker's messages the rate needs to be adjusted to the level of genuine traffic.

Mix strategies that take into account the number of messages queueing or that adapt their parameters according to the rate of arrival of messages have not been explicitly studied. The metric proposed should still be usable with them, although their delay characteristic function may be dependant of additional factors such as the rate of arrival of messages $\lambda_{\alpha}$. We expect the functions that depend upon the delay characteristic, such as the mean and variance of the latency, to still be usable.

Traffic analysis. More work needs to be done on how far the traffic analysis attack presented against stream-based anonymity systems can be exploited. Techniques from transient signal detection, as surveyed in [21], can be used as the foundation for a theory of traffic analysis. Some straightforward extensions of the work presented could be to simplify the extracted patterns, by retaining only the parts that are good at discriminating well the target stream, or at making the matching quicker. An experimental evaluation of how the length of the stream, or a more realistic distribution of packets, affects anonymity should also be easy to perform.

The attack assumes that an adversary can observe a "naked" stream somewhere in the network, in order to build a model later used for detection. An attacker might acquire the knowledge that a series of messages belong to the same stream by observing unpadded links at the edges of the mix network or by the means of subverted nodes. This assumption might be invalidated if cover traffic is used on all links, but variants of the attack might still work. Some preliminary results suggest that good models can be created despite this.

The attack can be performed by a passive adversary, without any knowledge of the relationships between packets on the attacked links. When an attacker knows the relationship between packets in the same stream, as a subverted node would, it is much easier to perform the statistical tests since the cover traffic can be discarded. In other words we expect most of the anonymity provided, up to the point where the path goes through a corrupt node, to be easily cancelled if the node applies our attack.

Furthermore the attacks are passive, in the sense that the attacker does not modify in any way the characteristics of the traffic. An active attacker would modulate the input traffic in order to maximise the chances of detecting it. They could introduce periodicity, allowing for periodic averaging for noise cancellation or injecting patterns of traffic specially designed to be easily detected. Unless the anonymity system takes special steps beyond delaying the traffic to destroy such structure, traffic streams will quickly be traceable.

## 5 Conclusions

The information theoretic anonymity metric is adapted to describe the properties of mixes that simply delay individual packets. We proved that the optimal delaying strategy is the exponential mix, for which we calculate the anonymity and latency.

A very powerfully attack is then presented that traces streams of messages following the same path through a delaying mix network. We present the conditions under which it is possible, and derive expressions that an adversary can use to assess his confidence. The attack is efficient enough to to be applied against whole networks by a global passive adversary. When performed by an adversary controlling subverted nodes or with the ability to shape traffic on the links, its effects are even more devastating. This attack is applicable to systems that provide real-time anonymous communications and leaves us very sceptical about the possibility of secure and efficient such constructions, in the absence of heavy amounts of cover traffic or delay.

**Acknowledgements** This work has been substantially improved after discussions with Ross Anderson, Markus Kuhn, Piotr Zielinski and Andrei Serjantov.

**References**

1. Adam Back, Ulf Möller, and Anton Stiglic. Traffic analysis attacks and trade-offs in anonymity providing systems. In Ira S. Moskowitz, editor, Information Hiding workshop (IH 2001), volume 2137 of LNCS, pages 245–257. Springer-Verlag, April 2001.
2. Oliver Berthold and Heinrich Langos. Dummy traffic against long term intersection attacks. In Roger Dingledine and Paul Syverson, editors, Privacy Enhancing Technologies workshop (PET 2002), volume 2482 of LNCS, pages 110–128. Springer-Verlag, 2002.
3. Oliver Berthold, Andreas Pfitzmann, and Ronny Standtke. The disadvantages of free MIX routes and how to overcome them. In H. Federrath, editor, Designing Privacy Enhancing Technologies, volume 2009 of LNCS, pages 30–45. Springer-Verlag, July 2000.
4. Philippe Boucher, Adam Shostack, and Ian Goldberg. Freedom systems 2.0 architecture. White paper, Zero Knowledge Systems, Inc., December 2000.
5. David Chaum. Untraceable electronic mail, return addresses, and digital pseudonyms. Communications of the ACM, 24(2):84–88, February 1981.
6. Claudia Diaz and Andrei Serjantov. Generalising mixes. In Roger Dingledine, editor, Privacy Enhancing Technologies workshop (PET 2003), volume 2760 of LNCS, pages 18–31, Dresden, Germany, March 2003. Springer-Verlag.
7. Michael J. Freedman and Robert Morris. Tarzan: A peer-to-peer anonymizing network layer. In Vijayalakshmi Atluri, editor, ACM Conference on Computer and Communications Security (CCS 2002), pages 193–206, Washington, DC, November 2002. ACM.
8. Ceki Gülcü and Gene Tsudik. Mixing E-mail with Babel. In Network and Distributed Security Symposium NDSS 96, pages 2–16, San Diego, California, February 1996. IEEE.
9. Dogan Kesdogan, Dakshi Agrawal, and Stefan Penz. Limits of anonymity in open environments. In Fabien A. P. Petitcolas, editor, Information Hiding workshop (IH 2002), volume 2578 of LNCS, pages 53–69, Noordwijkerhout, The Netherlands, 7–9 October 2002. Springer-Verlag.
10. Dogan Kesdogan, Jan Egner, and Roland Büschkes. Stop-and-Go MIXes: Providing probabilistic anonymity in an open system. In David Aucsmith, editor, Information Hiding workshop (IH 1998), volume 1525 of LNCS, pages 83–98, Portland, Oregon, USA, 14–17 April 1998. Springer-Verlag.
11. Brian N. Levine, Michael K. Reiter, Chenxi Wang, and Matthew Wright. Timing attacks in low-latency mix systems. In Finacial Cryptography (FC’04), 2004.
12. Jean-François Raymond. Traffic Analysis: Protocols, Attacks, Design Issues, and Open Problems. In Hannes Federrath, editor, Designing Privacy Enhancing Technologies, volume 2009 of LNCS, pages 10–29. Springer-Verlag, July 2000.
13. Michael G. Reed, Paul F. Syverson, and David M. Goldschlag. Anonymous connections and onion routing. IEEE Journal on Selected Areas in Communications, 16(4):482–494, May 1998.
14. Marc Rennhard and Bernhard Plattner. Introducing MorphMix: Peer-to-Peer based Anonymous Internet Usage with Collusion Detection. In workshop on Privacy in the Electronic Society (WPES 2002), Washington, DC, USA, November 2002.
15. Andrei Serjantov and George Danezis. Towards an information theoretic metric for anonymity. In Roger Dingledine and Paul Syverson, editors, Privacy Enhancing Technologies workshop (PET 2002), volume 2482 of LNCS, pages 41–53, San Francisco, CA, USA, 14–15 April 2002. Springer-Verlag.
16. Andrei Serjantov, Roger Dingledine, and Paul Syverson. From a trickle to a flood: Active attacks on several mix types. In Fabien A. P. Petitcolas, editor, Information Hiding workshop (IH 2002), volume 2578 of LNCS, pages 36–52, Noordwijkerhout, The Netherlands, 7–9 October 2002. Springer-Verlag.
17. Andrei Serjantov and Richard E. Newman. On the anonymity of timed pool mixes. In workshop on Privacy and Anonymity Issues in Networked and Distributed Systems, pages 427–434, Athens, Greece, May 2003. Kluwer.
18. Andrei Serjantov and Peter Sewell. Passive attack analysis for connection-based anonymity systems. In European Symposium on Research in Computer Security (ESORICS 2003), Gjovik, Norway, 13–15 October 2003.
19. Claude E. Shannon. A mathematical theory of communication. The Bell System Technical Journal, 27:379–423, 623–656, 1948.
20. Paul F. Syverson, Gene Tsudik, Michael G. Reed, and Carl E. Landwehr. Towards an analysis of onion routing security. In Hannes Federrath, editor, Designing Privacy Enhancing Technologies, volume 2009 of LNCS, pages 96–114, Berkeley, CA, USA, 25–26 July 2000. Springer-Verlag.
21. Zhen Wang and Peter Willett. A performance study of some transient detectors. IEEE transactions on signal processing, 48(9):2682–2685, September 2000.
22. Robert Weinstock. Calculus of variations. Dover publications, 1974. ISBN: 0486630692.