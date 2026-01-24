<!-- Page 1 -->

The Loopix Anonymity System
Ania Piotrowska
University College London
Jamie Hayes
University College London
Tariq Elahi
KU Leuven
Sebastian Meiser
University College London
George Danezis
University College London
Abstract
We present Loopix, a low-latency anonymous com-
munication system that provides bi-directional ‘third-
party’ sender and receiver anonymity and unobservabil-
ity. Loopix leverages cover trafﬁc and brief message de-
lays to provide anonymity and achieve trafﬁc analysis re-
sistance, including against a global network adversary.
Mixes and clients self-monitor the network via loops of
trafﬁc to provide protection against active attacks, and
inject cover trafﬁc to provide stronger anonymity and a
measure of sender and receiver unobservability. Service
providers mediate access in and out of a stratiﬁed net-
work of Poisson mix nodes to facilitate accounting and
off-line message reception, as well as to keep the num-
ber of links in the system low, and to concentrate cover
trafﬁc.
We provide a theoretical analysis of the Poisson mix-
ing strategy as well as an empirical evaluation of the
anonymity provided by the protocol and a functional im-
plementation that we analyze in terms of scalability by
running it on AWS EC2. We show that a Loopix relay
can handle upwards of 300 messages per second, at a
small delay overhead of less than 1.5ms on top of the de-
lays introduced into messages to provide security. Over-
all message latency is in the order of seconds – which
is low for a mix-system. Furthermore, many mix nodes
can be securely added to a stratiﬁed topology to scale
throughput without sacriﬁcing anonymity.
1
Introduction
In traditional communication security, the conﬁdential-
ity of messages is protected through encryption, which
exposes meta-data, such as who is sending messages to
whom, to network eavesdroppers. As illustrated by re-
cent leaks of extensive mass surveillance programs1, ex-
1See EFF’s guide at https://www.eff.org/files/2014/05/
29/unnecessary_and_disproportionate.pdf
posing such meta-data leads to signiﬁcant privacy risks.
Since 2004, Tor [19], a practical manifestation of
circuit-based onion routing, has become the most popu-
lar anonymous communication tool, with systems such
as Herd [32], Riposte [10], HORNET [9] and Vu-
vuzela [42] extending and strengthening this circuit-
based paradigm. Message-oriented architectures, based
on mix networks, have become unfashionable due to per-
ceived higher latencies, that cannot accommodate real-
time communications. However, unless cover trafﬁc is
employed, onion routing is susceptible to trafﬁc analy-
sis attacks [6] by an adversary that can monitor network
links between nodes. Recent revelations suggest that ca-
pabilities of large intelligence agencies approach that of
global passive observers—the most powerful form of this
type of adversary.
However,
it is not sufﬁcient to provide strong
anonymity against such an adversary while providing
low-latency communication. A successful system addi-
tionally needs to resist powerful active attacks and use an
efﬁcient, yet secure way of transmitting messages. More-
over, the system needs to be scalable to a large number
of clients, which makes classical approaches based on
synchronized rounds infeasible.
For this reason we reexamine and reinvent mix-based
architectures, in the form of the Loopix anonymity sys-
tem.
Loopix is resistant against powerful adversaries
who are capable of observing all communications and
performing active attacks. We demonstrate that such a
mix architecture can support low-latency communica-
tions that can tolerate small delays, at the cost of using
some extra bandwidth for cover trafﬁc. Delay, cover and
real trafﬁc can be ﬂexibly traded-off against each other
to offer resistance to trafﬁc analysis. Loopix provides
‘third-party’ anonymity, namely it hides the sender-
receiver relationships from third parties, but senders and
recipients can identify one another. This simpliﬁes the
design of the system, prevents abuse, and provides secu-
rity guarantees against powerful active adversaries per-
1
arXiv:1703.00536v1  [cs.CR]  1 Mar 2017


---

<!-- Page 2 -->

forming (n−1) attacks [38].
Loopix provides anonymity for private email or instant
messaging applications. For this reason, we adopt and
leverage an architecture by which users of Loopix are
associated with service providers that mediate their ac-
cess to a stratiﬁed anonymity system. Such providers
are only semi-trusted2, and are largely present to ensure
messages sent to off-line users can be retrieved at a later
time, maintain accounting, and enforce rate limiting. To
provide maximal ﬂexibility, Loopix only guarantees un-
reliable datagram transmission and is carried over UDP.
Reliable transport is left to the application as an end-to-
end concern [36].
Contributions. In this paper we make the following con-
tributions:
• We introduce Loopix, a new message-based anony-
mous communication system. It allows for a tun-
able trade-off between latency, genuine and cover
trafﬁc volume, to foil trafﬁc analysis.
• As a building block of Loopix we present the Pois-
son Mix, and provide novel theorems about its prop-
erties and ways to analyze it as a pool-mix. Pois-
son mixing does not require synchronized rounds,
can be used for low-latency anonymous communi-
cation, and provides resistance to trafﬁc analysis.
• We analyze the Loopix system against a strong,
global passive adversary. Moreover, we show that
Loopix provides resistance against active attacks,
such as trickling and ﬂooding. We also present a
methodology to estimate empirically the security
provided by particular mix topologies and other se-
curity parameters.
• We provide a full implementation of Loopix and
measure its performance and scalability in a cloud
hosting environment.
Outline.
The remainder of this paper is organized as
follows.
In Section 2, we present a brief, high-level
overview of Loopix and deﬁne the security goals and
threat model. In Section 3, we detail the design of Loopix
and describe Poisson mixes, upon which Loopix is based
and introduce their properties. In Section 4, we present
the analysis of Loopix security properties and discuss the
resistance against trafﬁc analysis and active attacks. In
Section 5, we discuss the implementation of Loopix sys-
tem and evaluate the performance. In Section 6, we sur-
vey related works and compare Loopix with recent de-
signs of anonymity systems. In Section 7, we discuss
remaining open problems and possible future work. Fi-
nally, we conclude in Section 8.
2Details about the threat model are in Section 2.3
2
Model and Goals
In this section, we ﬁrst outline the design of Loopix.
Then we discuss the security goals and types of adver-
saries which Loopix guarantees users’ privacy against.
2.1
High-level overview
Loopix is a mix network [7] based architecture allow-
ing users, distinguished as senders and receivers, to route
messages anonymously to each other using an infrastruc-
ture of mix servers, acting as relays. These mix servers
are arranged in a stratiﬁed topology [20] to ensure both
horizontal scalability and a sparse topology that concen-
trates trafﬁc on fewer links [11]. Each user is allowed to
access the Loopix network through their association with
a provider, a special type of mix server. Each provider
has a long-term relationship with its users and may au-
thenticate them, potentially bill them or discontinue their
access to the network. The provider not only serves as an
access point, but also stores users’ incoming messages.
These messages can be retrieved at any time, hence users
do not have to worry about lost messages when they are
off-line. In contrast to previous anonymous messaging
designs [42, 10], Loopix does not operate in determinis-
tic rounds, but runs as a continuous system. Additionally,
Loopix uses the Poisson mixing technique that is based
on the independent delaying of messages, which makes
the timings of packets unlinkable. This approach does
not require the synchronization of client-provider rounds
and does not degrade the usability of the system for tem-
porarily off-line clients. Moreover, Loopix introduces
different types of cover trafﬁc to foil de-anonymization
attacks.
2.2
Threat Model
Loopix assumes sophisticated,
strategic,
and well-
resourced adversaries concerned with linking users to
their communications and/or their communication part-
ner(s). As such, Loopix considers adversaries with three
distinct capabilities, that are described next.
Firstly, a global passive adversary (GPA) is able to ob-
serve all network trafﬁc between users and providers and
between mix servers. This adversary is able to observe
the entire network infrastructure, launch network attacks
such as BGP re-routing [3] or conduct indirect observa-
tions such as load monitoring and off-path attacks [24].
Thus, the GPA is an abstraction that represents many dif-
ferent classes of adversaries able to observe some or all
information between network nodes.
Secondly, the adversary has the ability to observe all
of the internal state of some corrupted or malicious mix
relays. The adversary may inject, drop, or delay mes-
2


---

<!-- Page 3 -->

sages. She also has access to, and operates, using the
secrets of those compromised parties. Furthermore, such
corrupted nodes may deviate from the protocol, or inject
malformed messages. A variation of this ability is where
the mix relay is also the provider node meaning that
the adversary additionally knows the mapping between
clients and their mailboxes. We say that the provider is
corrupt, but is restricted to being honest but curious. In
Loopix, we assume that a fraction of mix/provider relays
can be corrupted or are operated by the adversary.
Finally, the adversary has the ability to participate in
the Loopix system as a compromised user, who may de-
viate from the protocol. We assume that the adversary
can control a limited number of such users—excluding
Sybil attacks [21] from the Loopix threat model—since
we assume that honest providers are able to ensure that at
least a large fraction of their users base are genuine users
faithfully following all Loopix protocols. Thus, the frac-
tion of users controlled by the adversary may be capped
to a small known fraction of the user base. We further as-
sume that the adversary is able to control a compromised
user in a conversation with an honest user, and become a
conversation insider.
An adversary is always assumed to have the GPA ca-
pability, but other capabilities depend on the adversary.
We evaluate the security of Loopix in reference to these
capabilities.
2.3
Security Goals
The Loopix system aims to provide the following secu-
rity properties against both passive and active attacks—
including end-to-end correlation and (n −1) attacks.
These properties are inspired by the formal deﬁnitions
from Anoa [2]. All security notions assume a strong ad-
versary with information on all users, with up to one bit
of uncertainty. In the following we write {S →R} to de-
note a communication from the sender S to the receiver
R, {S →} to denote that there is a communication from S
to any receiver and {S ̸→} to denote that there is no com-
munication from S to any receiver (S may still send cover
messages). Analogously, we write {→R} to denote that
there is a communication from any sender to the receiver
R and {̸→R} to denote that there is no communication
from any sender to R (however, R may still receive cover
messages).
Sender-Receiver Third-party Unlinkability.
The
senders and receivers should be unlinkable by any unau-
thorized party.
Thus, we consider an adversary that
wants to infer whether two users are communicating. We
deﬁne sender-receiver third party unlinkability as the in-
ability of the adversary to distinguish whether {S1 →R1,
S2 →R2} or {S1 →R2,S2 →R1} for any concurrently
online honest senders S1,S2 and honest receivers R1,R2
of the adversary’s choice.
Loopix provides strong sender-receiver third-party
anonymity against the GPA even in collaboration with
corrupt mix nodes. We refer to Section 4.1.3 for our
analysis of the unlinkability provided by individual mix
nodes, to Section 4.3 for a quantitative analysis of the
sender-receiver third-party anonymity of Loopix against
the GPA and honest-but-curious mix nodes and to Sec-
tion 4.2 for our discussion on active attacks.
Sender online unobservability. Whether or not senders
are communicating should be hidden from an unautho-
rized party. We deﬁne sender online unobservability as
the inability of an adversary to decide whether a speciﬁc
sender S is communicating with any receiver {S →} or
not {S ̸→}, for any concurrently online honest sender S
of the adversary’s choice.
Loopix provides strong sender online unobservability
against the GPA in collaboration with an insider and even
against a corrupt provider. We refer to Section 4.1.2 for
our analysis of the latter.
Note, that sender online unobservability directly im-
plies the notion of sender anonymity where the adver-
sary tries to distinguish between two possible senders
communicating with a target receiver. Formally, {S1 →
R,S2 ̸→} or {S1 ̸→,S2 →R} for any concurrently online
honest senders S1 and S2 and any receiver of the adver-
sary’s choice. Loopix provides sender anonymity even
in light of a conversation insider, i.e., against a corrupt
receiver.
Receiver unobservability. Whether or not receivers are
part of a communication should be hidden from an unau-
thorized party.
We deﬁne receiver unobservability as
the inability of an adversary to decide whether there is
a communication from any sender to a speciﬁc receiver
R {→R} or not {̸→R}, for any online or ofﬂine honest
receiver R of the adversary’s choice.
Loopix
provides
strong
receiver
unobservability
against the GPA in collaboration with an insider, under
the condition of an honest provider. We show in Sec-
tion 4.1.2 how an honest provider assists the receiver in
hiding received messages from third party observers.
Note, that receiver unobservability directly implies the
notion of receiver anonymity where the adversary tries to
distinguish between two possible receivers in communi-
cation with a target sender. Formally, {S →R1,̸→R2}
or {̸→R1,S →R2} for any concurrently online honest
sender S and any two honest receivers R1,R2 of the ad-
versary’s choice. 3
3If the receiver’s provider is honest, Loopix provides a form of
receiver anonymity even in light of a conversation insider: a corrupt
sender that only knows the pseudonym of a receiver cannot learn which
honest client of a provider is behind the pseudonym.
3


---

<!-- Page 4 -->

## Table 1: Summary of notation

| Symbol | Description |
|---|---|
| N | Mix nodes |
| P | Providers |
| λL | Loop traffic rate (user) |
| λD | Drop cover traffic rate (user) |
| λP | Payload traffic rate (user) |
| l | Path length (user) |
| µ | The mean delay at mix M_i |
| λM | Loop traffic rate (mix) |

Non-Goals. Loopix provides anonymous unreliable
datagram transmission, as well as facilities the reply of
sent messages (through add-ons).
This choice allows
for ﬂexible trafﬁc management, cover trafﬁc, and trafﬁc
shaping. On the downside, higher-level applications us-
ing Loopix need to take care of reliable end-to-end trans-
mission and session management. We leave the detailed
study of those mechanisms as future work.
The provider based architecture supported by Loopix
aims to enable managed access to the network, support
anonymous blacklisting to combat abuse [26], and pay-
ments for differential access to the network [1]. How-
ever, we do not discuss these aspects of Loopix in this
work, and concentrate instead on the core anonymity fea-
tures and security properties described above.
3
The Loopix Architecture
In this section we describe the Loopix system in detail—
Figure 1 provides an overview. We also introduce the
notation used further in the paper, summarized in Sec-
tion 3.
3.1
System Setup
The Loopix system consists of a set of mix nodes N and
providers P. We consider a population of U users com-
municating through Loopix, each of which can act as
sender and receiver, denoted by indices Si, Ri, where i ∈
{1,...,U} respectively. Each entity of the Loopix infras-
tructure has its unique public-private key pair (sk, pk). In
order for a sender Si, with a key pair (skSi, pkSi), to send
a message to a receiver Rj, with a key pair (skRj, pkRj),
the sender needs to know the receiver’s Loopix network
location, i.e., the IP address of the user’s provider and an
identiﬁer of the user, as well as the public encryption key
pkRj. We assume this information can be made available
through a privacy-friendly lookup or introduction system
for initiating secure connection [31]. This is out of scope
for this work.
Storage
Storage
Storage
Storage
Users’ loop cover traﬃc
generates traﬃc
in two directions
Mixes can detect
n-1 attacks
Providers oﬀer
oﬄine storage
when user is oﬄine
Figure 1: The Loopix Architecture. Clients pass the messages
to the providers, which are responsible for injecting trafﬁc into
the network. The received messages are stored in individual
inboxes and retrieved by clients when they are online.
3.2
Format, Paths and Cover Trafﬁc
Message packet format.
All messages are end-to-end
encrypted and encapsulated into packets to be processed
by the mix network.
We use the Sphinx packet de-
sign [15], to ensure that intermediate mixes learn no ad-
ditional information beyond some routing information.
All messages are padded to the same length, which hides
the path length and the relay position and guarantees un-
linkability at each hop of the messages’ journey over the
network. Each message wrapped into the Sphinx packet
consists of two separate parts: a header H, carrying the
layered encryption of meta-data for each hop, and the
encrypted payload ρ of the message. The header pro-
vides each mix server on the path with conﬁdential meta-
data. The meta-data includes a single element of a cyclic
group (used to derive a shared encryption/decryption
key), the routing information and the message authenti-
cation code. We extend the Sphinx packet format to carry
additional routing information in the header to each in-
termediate relay, including a delay and additional ﬂags.
Path selection.
As opposed to onion routing, in Loopix
the communication path for every single message is cho-
sen independently, even between the same pair of users.
Messages are routed through l layers of mix nodes, as-
sembled in a stratiﬁed topology [11, 20]. Each mix node
is connected only with all the mix nodes from adjacent
layers. This ensures that few links are used, and those
few links are well covered in trafﬁc; stratiﬁed topolo-
gies mix well in few steps [20]. Providers act as the ﬁrst
and last layer of mix servers. To send a message, the
sender encapsulates the routing information described
above into a Sphinx packet which travels through their
provider, a sequence of mix servers, until it reaches the
4


---

<!-- Page 5 -->

receiver’s provider and ﬁnally the receiver. For each of
those hops the sender samples a delay from an exponen-
tial distribution with parameter µ, and includes it in the
routing information to the corresponding relay.
Sending messages and cover trafﬁc.
Users and mix
servers continuously generate a bed of real and cover
trafﬁc that is injected into the network. Our design guar-
antees that all outgoing trafﬁc sent by users can by mod-
eled by a Poisson process.
To send a message, a user packages their message into
a mix packet and places it into their buffer—a ﬁrst-in-
ﬁrst-out (FIFO) queue that stores all the messages sched-
uled to be sent.
Each sender periodically checks, following the expo-
nential distribution with parameter
1
λP , whether there is
any scheduled message to be sent in their buffer. If there
is a scheduled message, the sender pops this message
from the buffer queue and sends it, otherwise a drop
cover message is generated (in the same manner as a
regular message) and sent (depicted as the the four mid-
dle blue arrows in Figure 1). Cover messages are routed
through the sender’s provider and a chain of mix nodes to
a random destination provider. The destination provider
detects the message is cover based on the special drop
ﬂag encapsulated into the packet header, and drops it.
Thus, regardless of whether a user actually wants to send
a message or not, there is always a stream of messages
being sent according to a Poisson process Pois(λP).
Moreover, independently from the above, all users
emit separate streams of special indistinguishable types
of cover messages, which also follow a Poisson process.
The ﬁrst type of cover messages are Poisson distributed
loops emitted at rate λL. These are routed through the
network and looped back to the senders (the upper four
red arrows in Figure 1), by specifying the sending user as
the recipient. These “loops” inspire the system’s name.
Users also inject a separate stream of drop cover mes-
sages, deﬁned before, following the Poisson distribution
Pois(λD). Additionally, each user sends at constant time
a stream of pull requests to its provider in order to re-
trieve received messages, described in Section 3.2.
Each mix also injects their own loop cover trafﬁc,
drawn from a Poisson process with rate Pois(λM), into
the network.
Mix servers inject mix packets that are
looped through a path, made up of a subset of other mix
servers and one randomly selected provider, back to the
sending mix server, creating a second type of “loop”.
This loop originates and ends in a mix server (shown as
the lower four green arrows in Figure 1). In Section 4 we
examine how the loops and the drop cover messages help
protect against passive and active attacks.
Event i−1
Pool i−1
Event i
Pool i
Event i+1
Pool i+1
Event i+2
Figure 2: The Poisson Mix strategy mapped to a Pool mix
strategy. Each single message sending or receiving event leads
to a new pool of messages that are exchangeable and indistin-
guishable with respect to their departure times.
Message storing and retrieving.
Providers do not for-
ward the incoming mix packets to users but instead buffer
them. Users, when online, poll providers or register their
online status to download a ﬁxed subset of stored mes-
sages, allowing for the reception of the off-line mes-
sages. Recall that cover loops are generated by users
and traverse through the network and come back to the
sender. Cover loops serve as a cover set of outgoing and
incoming real messages. Whenever a user requests mes-
sages, their provider responds with a constant number of
messages, which includes their cover loop messages and
real messages. If the inbox of a particular user contains
fewer messages than this constant number, the provider
sends dummy messages to the sender up to that number.
3.3
The Poisson Mix Strategy
Loopix leverages cover trafﬁc to resist trafﬁc analysis
while still achieving low- to mid-latency. To this end
Loopix employs a mixing strategy that we call a Pois-
son Mix, to foil observers from learning about the cor-
respondences between input and output messages. The
Poisson Mix is a simpliﬁcation of the Stop-and-go mix
strategy [28]. A similar strategy has been used to model
trafﬁc in onion routing servers [13]. In contrast, recall
that in Loopix each message is source routed through an
independent route in the network.
The Poisson Mix functions as follows: mix servers
listen for the incoming mix packets and received mes-
sages are checked for duplication and decoded using the
mix node’s private keys.
The detected duplicates are
dropped. Next, the mix node extracts a subsequent mix
packet. Decoded mix packets are not forwarded immedi-
ately, but each of them is delayed according to a source
pre-determined delay di. Honest clients chose those de-
lays, independently for each hop, from an exponential
distribution with a parameter µ. We assume that this pa-
rameter is public and the same for all mix nodes.
Mathematical model of a Poisson Mix.
Honest
clients and mixes generate drop cover trafﬁc, loop traf-
ﬁc, and messaging trafﬁc following a Poisson process.
5


---

<!-- Page 6 -->

Aggregating Poisson processes results in a Poisson pro-
cess with the sum of their rates, therefore we may model
the streams of trafﬁc received by a Poisson mix as a Pois-
son process. It is the superposition of trafﬁc streams from
multiple clients. It has a rate λn depending on the number
of clients and the number of mix nodes.
Since this input process is a Poisson process and each
message is independently delayed using an exponential
distribution with parameter µ, the Poisson Mix may be
modeled as an M/M/∞queuing system – for we have
a number of well known theorems [4]. We know that
output stream of messages is also a Poisson process with
the parameter λn as the the input process. We can also
derive the distribution of the number of messages within
the Poisson Mix [33]:
Lemma 1. The mean number of messages in the Poisson
Mix with input Poisson process Pois(λ) and exponential
delay parameter µ at a steady state follows the Poisson
distribution Pois(λ/µ).
Those characteristics give the Poisson Mix its name.
This allows us to calculate the mean number of messages
perfectly mixed together at any time, as well as the prob-
ability that the number of messages falls below or above
certain thresholds.
The Poisson Mix, under the assumption that it approx-
imates an M/M/∞queue is a stochastic variant of a pool
mixing strategy [39]. Conceptually, each message send-
ing or receiving leads to a pool within which messages
are indistinguishable due to the memoryless property of
the exponential delay distribution.
Lemma 2 (Memoryless property [33]). For an exponen-
tial random variable X with parameter µ holds Pr[X >
s+t|X > t] = Pr[X > s].
Intuitively, any two messages in the same pool are
emitted next with equal probability – no matter how long
they have been waiting. As illustrated in Figure 2, the
receiving event i −1 leads to a pool of messages i −1,
until the sending event i. From the perspective of the ad-
versary observing all inputs and outputs, all messages in
the pool i−1 are indistinguishable from each other. Only
the presence of those messages in the pool is necessary to
characterize the hidden state of the mix (not their delay
so far). Relating the Poisson mix to a pool mix allows
us to compute easily and exactly both the entropy metric
for the anonymity it provides [37] within a trace (used in
Section 4.1.3). It also allows us to compute the likelihood
that an emitted message was any speciﬁc input message
used in our security evaluation.
4
Analysis of Loopix security properties
In this section we present the analytical and experimental
evaluation of the security of Loopix and argue its resis-
tance to trafﬁc analysis and active attacks.
4.1
Passive attack resistance
4.1.1
Message Indistinguishability
Loopix relies on the Sphinx packet format [15] to provide
bitwise unlinkability of incoming and outgoing messages
from a mix server; it does not leak information about the
number of hops a single message has traversed or the
total path length; and it is resistant to tagging attacks.
For Loopix, we make minor modiﬁcations to Sphinx
to allow auxiliary meta-information to be passed to dif-
ferent mix servers. Since all the auxiliary information is
encapsulated into the header of the packet in the same
manner as any meta-information was encapsulated in the
Sphinx design, the security properties are unchanged. An
external adversary and a corrupt intermediate mix node
or a corrupt provider will not be able to distinguish real
messages from cover messages of any type. Thus, the
GPA observing the network cannot infer any information
about the type of the transmitted messages, and interme-
diate nodes cannot distinguish real messages, drop cover
messages or loops of clients and other nodes from each
other. Providers are able to distinguish drop cover mes-
sage destined for them from other messages, since they
learn the drop ﬂag attached in the header of the packet.
Each mix node learns the delay chosen by clients for this
particular mix node, but all delays are chosen indepen-
dently from each other.
4.1.2
Client-Provider unobservability
In this section, we argue the sender and receiver un-
observability against different adversaries in our threat
model. Users emit payload messages following a Pois-
son distribution with parameter λP. All messages sched-
uled for sending by the user are placed within a ﬁrst-in-
ﬁrst-out buffer. According to a Poisson process, a single
message is popped out of the buffer and sent, or a drop
cover message is sent in case the buffer is empty. Thus,
from an adversarial perspective, there is always trafﬁc
emitted modeled by Pois(λP). Since clients send also
streams of cover trafﬁc messages with rates λL for loops
and λD for drop cover messages, the trafﬁc sent by the
client follows Pois(λP +λL +λD). Thus we achieve per-
fect sender unobservability, since the adversary cannot
tell whether a genuine message or a drop cover message
is sent.
When clients query providers for received messages,
the providers always send a constant number of messages
6


---

<!-- Page 7 -->

Inbox I
Inbox II
Inbox III
Figure 3:
Provider stores messages destined for assigned
clients in a particular inbox. When users pull messages from
the mix node, the provider generates cover messages to guar-
antee that the adversary cannot learn how many messages are
in the users inbox. The messages from the inbox and dummies
are indistinguishable.
to the client. If the number of messages in client’s inbox
is smaller than a constant threshold, the provider gen-
erates additional dummy messages. Thus, the adversary
observing the client-provider connection, as presented on
Figure 3, cannot learn how many messages were in the
user’s inbox. Note that, as long as the providers are hon-
est, the protection and receiver unobservability is perfect
and the adversary cannot learn any information about the
inbox and outbox of any client.
If the provider is dishonest, then they are still uncer-
tain whether a received message is genuine or the result
of a client loop – something that cannot be determined
from their bit pattern alone. However, further statistical
attacks may be possible, and we leave quantifying exact
security against this threat model as future work.
4.1.3
Poisson mix security
We ﬁrst show that a single honest Poisson mix provides a
measure of sender-receiver unlinkability. From the prop-
erties of Poisson mix, we know that the number of mes-
sages in the mix server at a steady state depends on the
ratio of the incoming trafﬁc (λ) and the delay parameter
(µ) (from Section 3.3). The number of messages in each
mix node at any time will on average be λ
µ . However, an
adversary observing the messages ﬂowing into and out
of a single mix node could estimate the exact number of
messages within a mix with better accuracy – hindered
only by the mix loop cover trafﬁc.
We ﬁrst consider, conservatively, the case where a mix
node is not generating any loops and the adversary can
count the exact number of messages in the mix. Let us
deﬁne on,k,l as an adversary A observing a mix in which
n messages arrive and are mixed together. The adversary
then observes an outgoing set of n−k messages and can
infer that there are now k < n messages in the mix. Next,
l additional messages arrive at the mix before any mes-
sage leaves, and the pool now mixes k+l messages. The
adversary then observes exactly one outgoing message
m and tries to correlate it with any of the n+l messages
which she has observed arriving at the mix node.
The following lemma is based on the memoryless
property of the Poisson mix. It provides an upper bound
on the probability that the adversary A correctly links the
outgoing message m with one of the previously observed
arrivals in observation on,k,l.
Theorem 1. Let m1 be any of the initial n messages in
the mix node in scenario on,k,l, and let m2 be any of the l
messages that arrive later. Then

$$
\Pr(m = m_1) = \frac{k}{n(l+k)} \tag{1}
$$

$$
\Pr(m = m_2) = \frac{1}{l+k} \tag{2}
$$

Note that the last l messages that arrived at the mix
node have equal probabilities of being the outgoing mes-
sage m, independently of their arrival times. Thus, the
arrival and departure times of the messages cannot be
correlated, and the adversary learns no additional infor-
mation by observing the timings. Note that
1
l+k is an
upper bound on the probability that the adversary A cor-
rectly links the outgoing message to an incoming mes-
sage.
Thus, continuous observation of a Poisson mix
leaks no additional information other than the number
messages present in the mix. We leverage those results
from about a single Poisson Mix to simulate the informa-
tion propagated withing a the whole network observed by
the adversary (c.f. Section 4.3).
We quantify the anonymity of messages in the mix
node empirically, using an information theory based met-
ric introduced in [37, 17].
We record the trafﬁc ﬂow
for a single mix node and compute the distribution of
probabilities that the outgoing message is the adversary’s
target message. Given this distribution we compute the
value of Shannon entropy (see Appendix A), a measure
of unlinkability of incoming to outgoing messages. We
compute this using the simpy package in Python. All
data points are averaged over 50 simulations.
Figure 4 depicts the change of entropy against an in-
creasing rate of incoming mix trafﬁc λ. We simulate the
dependency between entropy and trafﬁc rate for differ-
ent mix delay parameter µ by recording the trafﬁc ﬂow
and changing state of the mix node’s pool. As expected,
we observe that for a ﬁxed delay, the entropy increases
when the rate of trafﬁc increases. Higher delay also re-
sults in an increase in entropy, denoting a larger potential
anonymity set, since more messages are mixed together.
In case the mix node emits loop cover trafﬁc, the ad-
versary with observation on,k,l, tries to estimate the prob-
ability that the observed outgoing message is a particular
7


---

<!-- Page 8 -->

100
150
200
250
300
350
400
450
500
Rate of incoming traffic ( )
0
2
4
6
8
10
12
14
16
Entropy
 = 200
 = 20
 = 2
 = 0.2
 = 0.02
Figure 4: Entropy versus the changing rate of the incoming
trafﬁc for different delays with mean 1
µ . In order to measure
the entropy we run a simulation of trafﬁc arriving at a single
Loopix mix node.
target message she observed coming into the mix node.
An outgoing message can be either input message or a
loop message generated by the mix node – resulting in
additional uncertainty for the adversary.
Theorem 2. Let m1 be any of the initial n messages in
the mix node in scenario on,k,l, and let m2 be any of the
l messages that arrive later. Let λM denote the rate at
which mix node generates loop cover trafﬁc. Then,

$$
\Pr(m = m_2) = \frac{k}{n}\cdot\frac{\mu}{(l+k)\mu+\lambda_M}
$$

$$
\Pr(m = m_1) = \frac{\mu}{(l+k)\mu+\lambda_M}
$$

We refer to Appendix A for the proof. We conclude
that the loops generated by the mix node obfuscate the
adversary’s view and decrease the probability of success-
fully linking input and output of the mix node. In Sec-
tion 4.2 we show that those types of loops also protect
against active attacks.
4.2
Active-attack Resistance
Lemma 1 gives the direct relationship between the ex-
pected number of messages in a mix node, the rate of in-
coming trafﬁc, and the delay induced on a message while
transiting through a mix. By increasing the rate of cover
trafﬁc, λD and λL, users can collectively maintain strong
anonymity with low message delay. However, once the
volume of real communication trafﬁc λP increases, users
can tune down the rate of cover trafﬁc in comparison
to the real trafﬁc, while maintaining a small delay and
be conﬁdent their messages are mixed with a sufﬁcient
number of messages.
In the previous section, we analyze the security prop-
erties of Loopix when the adversary observes the state of
a single mix node and the trafﬁc ﬂowing through it. We
showed, that the adversary’s advantage is bounded due
to the indistinguishability of messages and the memory-
less property of the Poisson mixing strategy. We now in-
vestigate how Loopix can protect users’ communications
against active adversaries conducting the (n−1) attack.
4.2.1
Active attacks
We consider an attack at a mix node where an adversary
blocks all but a target message from entering in order
to follow the target message when it exits the mix node.
This is referred to as an (n-1) attack [38].
A mix node needs to distinguish between an active at-
tack and loop messages dropped due to congestion. We
assume that each mix node chooses some public param-
eter r, which is a fraction of the number of loops that
are expected to return. If the mix node does not see this
fraction of loops returning they alter their behavior. In
extremis such a mix could refuse to emit any messages
– but this would escalate this attack to full denial-of-
service. A gentler approach involves generating more
cover trafﬁc on outgoing links [16].
To attempt an (n-1) attack, the adversary could simply
block all incoming messages to the mix node except for a
target message. The Loopix mix node can notice that the
self-loops are not returning and deduce it is under attack.
Therefore, an adversary that wants to perform a stealthy
attack has to be judicious when blocking messages, to
ensure that a fraction r of loops return to the mix node,
i.e. the adversary must distinguish loop cover trafﬁc from
other types of trafﬁc. However, trafﬁc generated by mix
loops is indistinguishable from other network trafﬁc and
they cannot do this better than by chance.
Therefore
given a threshold r = λM
s ,s ∈R>1 of expected returning
loops when a mix observes fewer returning it deploys ap-
propriate countermeasures.
We analyze this strategy: since the adversary cannot
distinguish loops from other trafﬁc the adversary can do
no better than block trafﬁc uniformly such that a fraction
R = λ
s = λR+λM
s
enter the mix, where λR is the rate of
incoming trafﬁc that is not the mix node’s loops. If we
assume a steady state, the target message can expect to
be mixed with λR
s·µ messages that entered this mix, and
λM
µ loop messages generated at the mix node. Thus, the
probability of correctly blocking a sufﬁcient number of
messages entering the mix node so as not to alter the be-
havior of the mix is:
$$
\Pr(x = \mathrm{target}) = \frac{1}{\lambda_R/(s\mu) + \lambda_M/\mu}
= \frac{s\mu}{s\lambda_M + \lambda_R}.
$$

Due to the stratiﬁed topology, providers are able to dis-
tinguish mix loop messages sent from other trafﬁc, since
they are unique in not being routed to or from a client.
This is not a substantial attack vector since mix loop
messages are evenly distributed among all providers, of
8


---

<!-- Page 9 -->

which a small fraction are corrupt and providers do not
learn which mix node sent the loop to target it.
4.3
End-to-End Anonymity Evaluation
We evaluate the sender-receiver third-party unlinkability
of the full Loopix system through an empirical analysis
of the propagation of messages in the network. Our key
metric is the expected difference in likelihood that a mes-
sage leaving the last mix node is sent from one sender
in comparison to another sender. Given two probabilities
p0 = Pr[S0] and p1 = Pr[S1] that the message was sent by
senders S0 and S1, respectively, we calculate
$$
\varepsilon = \left|\log\left(\frac{p_0}{p_1}\right)\right|. \tag{3}
$$

To approximate the probabilities p0 and p1, we pro-
ceed as follows. We simulate U = 100 senders that gen-
erate and send messages (both payload and cover mes-
sages) with a rate λ = 2. Among them are two challenge
senders S0 and S1 that send payload messages at a con-
stant rate, i.e, they add one messages to their sending
buffer every time unit.
Whenever a challenge sender S0 or S1 sends a payload
message from its buffer, we tag the message with a la-
bel S0 or S1, respectively. All other messages, including
messages from the remaining 98 clients and the cover
messages of S0 and S1 are unlabeled. At every mix we
track the probability that an outgoing message is labeled
S0 or S1, depending on the messages that entered the mix
node and the number of messages that already left the
mix node, as in Theorem 1. Thus, messages leaving a
mix node carry a probability distribution over labels S0,
S1, or ‘unlabeled’. Corrupt mix nodes, assign to outgoing
messages their input distributions. The probabilities nat-
urally add up to 1. For example, a message leaving a mix
can be labeled as {S0 : 12%,S1 : 15%,unlabeled : 73%}.
In a burn-in phase of 2500 time units, the 98 senders
without S0 or S1 communicate. Then we start the two
challenge senders and then simulate the network for an-
other 100 time units, before we compute the expected
difference in likelihood metric. We pick a ﬁnal mix node
and using probabilities of labels S0 and S1 for any mes-
sage in the pool we calculate ε as in Equation (3).
This is a conservative approximation: we tell the ad-
versary which of the messages leaving senders S0 and S1
are payload messages; and we do not consider mix or
client loop messages confusing them. 4 However, when
we calculate our anonymity metric at a mix node we as-
sume this mix node to be honest.
4The soundness of our simpliﬁcation can be seen by the fact that we
could tell the adversary which messages are loops and the adversary
could thus ignore them. This is equivalent to removing them, as an
adversary could also simulate loop messages.
 0.2
 0.4
 0.6
 0.8
 1.0
 1.2
 1.4
 1.6
 1.8
 2.0
Rate of the delay ( )
0.0
0.2
0.4
0.6
0.8
1.0
Likelihood difference 
Figure 5: Likelihood difference ε depending on the delay pa-
rameter µ of mix nodes. We use λ = 2, a topology of 3 layers
with 3 nodes per layer and no corruption.
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
Number of layers (l)
0.0
0.2
0.4
0.6
0.8
1.0
Likelihood difference 
Figure 6: Likelihood difference ε depending on the number of
layers of mix nodes with 3 mix nodes per layer. We use λ = 2,
µ = 1, and no corruption.
4.3.1
Results
We compare our metric for different parameters: depend-
ing on the delay parameter µ, the number of layers in our
topology l and the percentage of corrupted mix nodes in
the network. All of the below simulations are averaged
over 100 repetitions and the error bars are deﬁned by the
standard deviation.
Delay.
Increasing the average delay (by decreasing pa-
rameter µ) with respect to the rate of message sending
λ immediately increases anonymity (decreases ε) (Fig-
ure 5). For µ = 2.0 and λ/µ = 1, Loopix still provides a
weak form of anonymity. As this fraction increases, the
log likelihood ratio grow closer and closer to zero. We
consider values λ/µ ≥2 to be a good choice in terms of
anonymity.
Number of layers.
By increasing the number of layers
of mix nodes, we can further strengthen the anonymity of
Loopix users. As expected, using only one or two layers
of mix nodes leads to high values of adversary advantage
ε. An increasing number of layers ε approaches zero
(Figure 6). We consider a number of 3 or more layers
to be a good choice. We believe the bump between 5–8
9


---

<!-- Page 10 -->

0
10
20
30
40
50
60
70
80
90
100
Percentage of corrupt mix nodes
0
2
4
6
8
10
Likelihood difference 
Figure 7: Likelihood difference ε depending on the percentage
of (passively) corrupted mix nodes. We use λ = 2, µ = 1 and
a topology of 3 layers with 3 nodes per layer.
layers is due to messages not reaching latter layers within
100 time units, however results from experiments with
increased duration do not display such a bump.
Corruption.
Finally, we analyze the impact that cor-
rupt mix nodes have on the adversary advantage ε (Fig-
ure 7). We assume that the adversary randomly corrupts
mix nodes. Naturally, the advantage ε increases with the
percentage of corrupt mix nodes in the network. In a
real-world deployment we do not expect a large fraction
of mix nodes to be corrupt. While the adversary may
be able to observe the entire network, to control a large
number of nodes would be more costly.
5
Performance Evaluation
Implementation.
We implement the Loopix system
prototype in 4000 lines of Python 2.7 code for mix
nodes, providers and clients, including unit-tests, de-
ployment, and orchestration code. Loopix source code
is available under an open-source license5. We use the
Twisted 15.5.0 network library for networking; as well
as the Sphinx mix packet format6 and the cryptographic
tools from the petlib7 library.
We modify Sphinx to
use NIST/SEGS-p224 curves and to accommodate ad-
ditional information inside the packet, including the de-
lay for each hop and auxiliary ﬂags. We also optimize its
implementation leading to processing times per packet of
less than 1ms.
The most computationally expensive part of Loopix
is messages processing and packaging, which involves
cryptographic operations. Thus, we implement Loopix
as a multi-thread system, with cryptographic processing
happening in a thread pool separated from the rest of the
operations in the main thread loop. To recover from con-
gestion we implement active queue management based
5Public Github repository URL obscured for review.
6http://sphinxmix.readthedocs.io/en/latest/
7http://petlib.readthedocs.org
0
20
40
60
80
100
120
140
160
Rate of sending per client ( ) per minute
0
50
100
150
200
250
300
Messages processed per sec
All traffic
Payload traffic
Figure 8: Overall bandwidth and good throughput per second
for a single mix node.
on a PID controller and we drop messages when the size
of the queue reaches a (high) threshold.
Experimental Setup.
We present an experimental per-
formance evaluation of the Loopix system running on
the AWS EC2 platform.
All mix nodes and providers
run as separate instances. Mix nodes are deployed on
m4.4xlarge instances running EC2 Linux on 2.3GHz
machines with 64GB RAM memory. Providers, since
they handle more trafﬁc, storage and operations, are de-
ployed on m4.16xlarge instances with 256GB RAM.
We select large instances to ensure that the providers are
not the bottleneck of the bandwidth transfer, even when
users send messages at a high rate. This reﬂects real-
world deployments where providers are expected to be
well-resourced. We also run one m4.16xlarge instance
supporting 500 clients. We highlight that each client runs
as a separate process and uses a unique port for trans-
porting packets. Thus, our performance measurements
are obtained by simulating a running system with inde-
pendent clients8. In order to measure the system per-
formance, we run six mix nodes, arranged in a stratiﬁed
topology with three layers, each layer composed of two
mix nodes. Additionally, we run four providers, each
serving approximately 125 clients.
The delays of all
the messages are drawn from an exponential distribution
with parameter µ, which is the same for all mix servers
in the network. All measurements are take from network
trafﬁc dumps using tcpdump.
Bandwidth.
First, we evaluate the maximum band-
width of mix nodes by measuring the rate at which a
single mix node processes messages, for an increasing
overall rate at which users send messages.
We set up the ﬁxed delay parameter µ = 1000 (s.t.
the average delay is 1ms). We have 500 clients actively
8Other works, e.g. [41, 42], report impressive evaluations in terms
of scale, but in fact are simple extrapolations and not based on empirical
results.
10


---

<!-- Page 11 -->

0
50
100
150
200
250
300
350
400
450
500
Number of clients
0.0
0.5
1.0
1.5
2.0
2.5
3.0
3.5
4.0
Latency Overhead (ms)
Figure 9: Latency overhead of the system where 50 to 500
users simultaneously send trafﬁc at rates λP = λL = λD = 10
per minute and mix nodes generate loop cover trafﬁc at rate
λM = 10 per minute. We assume that there is not additional
delay added to the messages by the senders.
sending messages at rate λ each, which is the sum of pay-
load, loop and drop rates, i.e., λ = Pois(λL + λD + λP).
We start our simulation with parameters λL = λD = 1
and λP = 3 messages per minute for a single client. Mix
nodes send loop cover trafﬁc at rate starting from λM = 1.
Next, we periodically increase each Poisson rate by an-
other 2 messages per minute.
In order to measure the overall bandwidth, i.e. the
number of all messages processed by a single mix node,
we use the network packet analyzer tcpdump.
Since
real and cover message packets are indistinguishable, we
measure the good throughput by encapsulating an addi-
tional, temporary, typeFlag in the packet header for this
evaluation, which leaks to the mix the message type—
real or cover—and is recorded.
Figure 8 illustrates the number of total messages and
the number of payload messages that are processed by
a single mix node versus the overall sending rate λ of a
single user. We observe that the bandwidth of the mix
node increases linearly until it reaches around 225 mes-
sages per second. After that point the performance of
the mix node stabilizes and we observe a much smaller
growth. We highlight that the amount of real trafﬁc in the
network depends on the parameter λP within λ. A client
may chose to tune up the rate of real messages sent, by
tuning down the rate of loops and drop messages – at
the potential loss of security in case less cover trafﬁc is
present in the system overall. Thus, depending on the
size of the honest user population in Loopix, we can in-
crease the rate of goodput.
Latency Overhead & Scalability.
End-to-end latency
overhead is the cost of routing and decoding relayed mes-
sages, without any additional artiﬁcial delays. We run
simulations to measure its sensitivity to the number of
users participating in the system.
We measure the time needed to process a single packet
by a mix node, which is approximately 0.6ms. This cost
0
1
2
3
4
5
6
7
Latency (s)
0.0
0.1
0.2
0.3
0.4
0.5
0.6
Frequency
Gamma distribution fit
Figure 10: End-to-end latency histogram measured through
timing mix node loops. We run 500 users actively commu-
nicating via Loopix at rates λP = λL = λD = 60 per minute and
λM = 60 per minute. The delay for each hop is drawn from
Exp(2). The latency of the message is determined by the as-
signed delay and ﬁts the Gamma distribution with mean 1.93
and standard deviation 0.87.
is dominated by the scalar multiplication of an elliptic
curve point and symmetric cryptographic operations. For
the end-to-end measurement, we run Loopix with a setup
where all users have the same rates of sending real and
cover messages, such that λP = λD = λL = 10 messages
per minute and mix servers generate loops at rate λM =
10 messages per minute. All clients set a delay of 0.0
seconds for all the hops of their messages – to ensure
we only measure the system overhead, not the artiﬁcial
mixing delay.
Figure 9 shows that increasing the number of online
clients, from 50 to 500, raises the latency overhead by
only 0.37ms. The variance of the processing delay in-
creases with the amount of trafﬁc in the network, but
more clients do not signiﬁcantly inﬂuence the average
latency overhead. Neither the computational power of
clients nor mix servers nor the communication between
them seem to become bottlenecks for these rates. Those
results show that the increasing number of users in the
network does not lead to any bottleneck for our parame-
ters. The measurements presented here are for a network
of 6 mix nodes, however we can increase the system ca-
pacity by adding more servers. Thus, Loopix scales well
for an increasing number of users.
We also investigate how increasing the delays through
Poisson Mixing with µ = 2 affects the end-to-end la-
tency of messages. We measure this latency through tim-
ing mix heartbeat messages traversing the system. Fig-
ure 10 illustrates that when the mean delay 1/µ sec. is
higher than the processing time (∼1ms−2ms), the end-
to-end latency is determined by this delay, and follows
the Gamma distribution with parameter being the sum of
the exponential distribution parameter over the number
of servers on the path. The good ﬁt to a gamma distribu-
11


---

<!-- Page 12 -->

tion provides evidence that the implementation of Loopix
is faithful to the queuing theory models our analysis as-
sumes.
6
Related Work
All anonymous communication designs share the com-
mon goal of hiding users’ communication patterns
from adversaries.
Simultaneously minimizing latency
and communication overhead while still providing high
anonymity is challenging. We survey other anonymous
systems and compare them with Loopix (a summary is
provided in Table 2).
Early designs.
Designs based on Chaum’s mixes [7]
can support both high and low latency communication;
all sharing the basic principles of mixing and layered
encryption. Mixmaster [34] supports sender anonymity
using messages encryption but does not ensure receiver
anonymity. Mixminion [14] uses ﬁxed sized messages
and supports anonymous replies and ensures forward
anonymity using link encryption between nodes. As a
defense against trafﬁc analysis, but at the cost of high-
latencies, both designs delay incoming messages by col-
lecting them in a pool that is ﬂushed every t seconds (if
a ﬁxed message threshold is reached).
In contrast, Onion routing [25] was developed for low-
latency anonymous communication. Similar to mix de-
signs, each packet is encrypted in layers, and is decrypted
by a chain of authorized onion routers. Tor [19], the
most popular low-latency anonymity system, is an over-
lay network of onion routers. Tor protects against sender-
receiver message linking against a partially global adver-
sary and ensures perfect forward secrecy, integrity of the
messages, and congestion control. However, Tor is vul-
nerable to trafﬁc analysis attacks, if an adversary can ob-
serve the ingress and egress points of the network.
Recent designs.
Vuvuzela [42] protects against both
passive and active adversaries as long as there is one
honest mix node. Since Vuvuzela operates in rounds, of-
ﬂine users lose the ability to receive messages and all
messages must traverse a single chain of relay servers.
Loopix does not operate in rounds, allows off-line users
to receive messages and uses parallel mix nodes to im-
prove the scalability of the network.
Stadium [41] and AnonPop [23] reﬁne Vuvuzela; both
operating in rounds making the routing of messages de-
pendent on the dynamics of others. Stadium is scalable,
but it lacks ofﬂine storage, whereas AnonPop does pro-
vide ofﬂine message storage. Loopix also provides both
properties, and because it operates continuously avoids
user synchronization issues.
Riposte [10] is based on a write PIR scheme in which
users write their messages into a database, without re-
vealing the row into which they wrote to the database
server. Riposte enjoys low communication-overhead and
protects against trafﬁc analysis and denial of service at-
tacks, but requires long epochs and a small number of
clients writing into the database simultaneously. In con-
trast to Loopix, it is suitable for high-latency applica-
tions.
Dissent [8], based on DC-networks [8], offers re-
silience against a GPA and some active attacks, but at sig-
niﬁcantly higher delays and scales to only several thou-
sand clients.
Rifﬂe [30] introduces a new veriﬁable shufﬂe tech-
nique to achieve sender anonymity.
Using PIR, Rif-
ﬂe guarantees receiver anonymity in the presence of an
active adversary, as well as both sender and receiver
anonymity, but it cannot support a large user base. Rifﬂe
also utilizes rounds protect trafﬁc analysis attacks. Rifﬂe
is not designed for Internet-scale anonymous communi-
cation, like Loopix, but for supporting intra-group com-
munication.
Finally, Atom [29] combines a number of novel tech-
niques to provide mid-latency communication, strong
protection against passive adversaries and uses zero
knowledge proofs between servers to resist active at-
tacks. Performance scales horizontally, however latency
comparisons between Loopix and Atom are difﬁcult due
to the dependence on pre-computation in Atom.
Un-
like Loopix, Atom is designed for latency tolerant uni-
directional anonymous communication applications with
only sender anonymity in mind.
7
Discussion & Future Work
As shown in Section 4.1, the security of Loopix heavily
depends on the ratio of the rate of trafﬁc sent through the
network and the mean delay at every mix node. Opti-
mization of this ratio application dependent. For appli-
cations with small number of messages and delay toler-
ance, a small amount of cover trafﬁc can guarantee secu-
rity.
Loopix achieves its stated security and performance
goals. However, there are many other facets of the de-
sign space that have been left for future work. For in-
stance, reliable messages delivery, session management,
and ﬂow control while all avoiding inherent risks, such as
statistical disclosure attacks [12], are all fruitful avenues
of pursuit.
We also leave the analysis of replies to messages as
future work.
Loopix currently allows two methods if
the receiver does not already know the sender a priori:
we either attach the address of the sender to each mes-
sage payload, or provide a single-use anonymous reply
block [14, 15], which enables different use-cases.
12


---

<!-- Page 13 -->

## Table 2: Comparison of popular anonymous communication systems

| System | Low Latency | Low Communication Overhead | Scalable Deployment | Asynchronous Messaging† | Active Attack Resistant | Offline Storage* | Resistance to GPA |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Loopix | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Dissent [43] | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ |
| Vuvuzela [42] | ✗ | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ |
| Stadium [41] | ✗ | ✓ | ✓ | ✗ | ✓ | ✗ | ✓ |
| Riposte [10] | ✗ | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ |
| Atom [29] | ✗ | ✓ | ✓ | ✗ | ✓ | ✗ | ✓ |
| Riffle [30] | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ |
| AnonPoP [23] | ✗ | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ |
| Tor [19] | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |

**Table 2:** Comparison of popular anonymous communication systems.  
By *, we mean if the design intentionally incorporates provisions for delivery of messages when a user is offline, perhaps for a long period of time.  
By †, we mean that the system operates continuously and does not depend on synchronized rounds for its security properties and users do not need to coordinate to communicate together.

The Loopix architecture deliberately relies on estab-
lished providers to connect to and authenticate end-users.
This architecture brings a number of potential beneﬁts,
such as resistance to Sybil attacks, enabling anonymous
blacklisting [26] and payment gateways [1] to mitigate
ﬂooding attacks and other abuses of the system, and pri-
vacy preserving measurements [22, 27] about client and
network trends and the security stance of the system. All
of this analysis is left for future work.
It is also apparent that an efﬁcient and secure pri-
vate lookup system, one that can deliver network state
and keying information to its users, is necessary to sup-
port modern anonymous communications.
Proposals
of stand-alone ‘presence’ systems such as DP5 [5] and
MP3 [35] provide efﬁcient lookup methods, however,
we anticipate that tight integration between the lookup
and anonymity systems may bring mutual performance
and security beneﬁts, which is another avenue for future
work.
8
Conclusion
The Loopix mix system explores the design space fron-
tiers of low-latency mixing.
We balance cover trafﬁc
and message delays to achieve a tunable trade-off be-
tween real trafﬁc and cover trafﬁc, and between latency
and good anonymity.
Low-latency incentivizes early
adopters to use the system, as they beneﬁt from good
performance. Moreover, the cover trafﬁc introduced by
both clients and mix servers provides security in the pres-
ence of a smaller user-base size. In turn this promotes
growth in the user-base leading on one hand to greater
security [18], and on the other a tuning down of cover
trafﬁc over time.
Loopix is the ﬁrst system to combine a number of
best-of-breed techniques: we provide deﬁnitions inspired
by AnoA [2] for our security properties; improve the
analysis of simpliﬁed variants of stop-and-go-mixing
as a Poisson mix [28]; we use restricted topologies
to promote good mixing [20]; we deploy modern ac-
tive attack mitigations based on loops [16]; and we use
modiﬁed modern cryptographic packet formats, such as
Sphinx [15], for low information leakage. Our design,
security and performance analysis, and empirical eval-
uation shows they work well together to provide strong
security guarantees.
The result of composing these different techniques –
previously explored as separate and abstract design op-
tions – is a design that is strong against global net-
work level adversaries without the very high-latencies
traditionally associated with mix systems [34, 14].
Thus, Loopix revitalizes message-based mix systems and
makes them competitive once more against onion rout-
ing [25] based solutions that have dominated the ﬁeld
of anonymity research since Tor [19] was proposed in
2004.
Acknowledgments
We thank Claudia Diaz and Mary
Maller for the helpful discussions. In memory of Len
Sassaman. This work was supported by NSERC through
a Postdoctoral Fellowship Award, the Research Coun-
cil KU Leuven: C16/15/058, the European Commis-
sion through H2020-DS-2014-653497 PANORAMIX,
the EPSRC Grant EP/M013-286/1, and the UK Govern-
ment Communications Headquarters (GCHQ), as part of
University College London’s status as a recognised Aca-
demic Centre of Excellence in Cyber Security Research.
13


---

<!-- Page 14 -->

References
[1] ANDROULAKI, E., RAYKOVA, M., SRIVATSAN,
S., STAVROU, A., AND BELLOVIN, S. M. PAR:
Payment for Anonymous Routing. In Privacy En-
hancing Technologies, 8th International Sympo-
sium, PETS 2008, Leuven, Belgium, July 23-25,
2008, Proceedings (2008), pp. 219–236.
[2] BACKES, M., KATE, A., MANOHARAN, P.,
MEISER, S., AND MOHAMMADI, E.
AnoA: A
Framework for Analyzing Anonymous Communi-
cation Protocols.
In Computer Security Founda-
tions Symposium (CSF), 2013 IEEE 26th (2013),
IEEE, pp. 163–178.
[3] BALLANI, H., FRANCIS, P., AND ZHANG, X. A
study of preﬁx hijacking and interception in the In-
ternet. In ACM SIGCOMM Computer Communica-
tion Review (2007), vol. 37, ACM, pp. 265–276.
[4] BOLCH, G., GREINER, S., DE MEER, H., AND
TRIVEDI, K. S. Queueing networks and Markov
chains: modeling and performance evaluation with
computer science applications. John Wiley & Sons,
2006.
[5] BORISOV, N., DANEZIS, G., AND GOLDBERG, I.
DP5: A private presence service. Proceedings on
Privacy Enhancing Technologies 2015, 2 (2015),
4–24.
[6] CAI, X., ZHANG, X. C., JOSHI, B., AND JOHN-
SON, R. Touching from a distance: Website ﬁnger-
printing attacks and defenses. In Proceedings of the
2012 ACM conference on Computer and communi-
cations security (2012), ACM, pp. 605–616.
[7] CHAUM, D.
Untraceable Electronic Mail, Re-
turn Addresses, and Digital Pseudonyms. Commun.
ACM 24, 2 (1981), 84–88.
[8] CHAUM, D. The dining cryptographers problem:
Unconditional sender and recipient untraceability.
Journal of cryptology 1, 1 (1988), 65–75.
[9] CHEN,
C.,
ASONI,
D. E.,
BARRERA,
D.,
DANEZIS, G., AND PERRIG, A. HORNET: High-
speed Onion Routing at the Network Layer. In Pro-
ceedings of the 22nd ACM SIGSAC Conference on
Computer and Communications Security, Denver,
CO, USA, October 12-6, 2015 (2015), pp. 1441–
1454.
[10] CORRIGAN-GIBBS, H., BONEH, D., AND MAZ-
IÈRES, D.
Riposte: An anonymous messaging
system handling millions of users. In 2015 IEEE
Symposium on Security and Privacy (2015), IEEE,
pp. 321–338.
[11] DANEZIS, G. Mix-networks with restricted routes.
In International Workshop on Privacy Enhancing
Technologies (2003), Springer, pp. 1–17.
[12] DANEZIS, G.
Statistical disclosure attacks.
In
Security and Privacy in the Age of Uncertainty.
Springer, 2003, pp. 421–426.
[13] DANEZIS, G. The Trafﬁc Analysis of Continuous-
Time Mixes. In Privacy Enhancing Technologies,
4th International Workshop, PET 2004, Toronto,
Canada, May 26-28, 2004, Revised Selected Papers
(2004), pp. 35–50.
[14] DANEZIS, G., DINGLEDINE, R., AND MATHEW-
SON, N. Mixminion: Design of a type III anony-
mous remailer protocol. In Security and Privacy,
2003. Proceedings. 2003 Symposium on (2003),
IEEE, pp. 2–15.
[15] DANEZIS, G., AND GOLDBERG, I.
Sphinx: A
compact and provably secure mix format. In Se-
curity and Privacy, 2009 30th IEEE Symposium on
(2009), IEEE, pp. 269–282.
[16] DANEZIS, G., AND SASSAMAN, L. Heartbeat traf-
ﬁc to counter (n-1) attacks: red-green-black mixes.
In Proceedings of the 2003 ACM workshop on Pri-
vacy in the electronic society (2003), ACM, pp. 89–
93.
[17] DIAZ, C., SEYS, S., CLAESSENS, J., AND PRE-
NEEL, B. Towards measuring anonymity. In In-
ternational Workshop on Privacy Enhancing Tech-
nologies (2002), Springer, pp. 54–68.
[18] DINGLEDINE,
R.,
AND
MATHEWSON,
N.
Anonymity Loves Company:
Usability and the
Network Effect. In WEIS (2006).
[19] DINGLEDINE,
R.,
MATHEWSON,
N.,
AND
SYVERSON, P. Tor: The second-generation onion
router. Tech. rep., DTIC Document, 2004.
[20] DINGLEDINE, R., SHMATIKOV, V., AND SYVER-
SON, P. Synchronous batching: From cascades to
free routes. In International Workshop on Privacy
Enhancing Technologies (2004), Springer, pp. 186–
206.
[21] DOUCEUR, J. R.
The sybil attack.
In Interna-
tional Workshop on Peer-to-Peer Systems (2002),
Springer, pp. 251–260.
14


---

<!-- Page 15 -->

[22] ELAHI, T., DANEZIS, G., AND GOLDBERG, I.
Privex: Private collection of trafﬁc statistics for
anonymous communication networks. In Proceed-
ings of the 2014 ACM SIGSAC Conference on Com-
puter and Communications Security (2014), ACM,
pp. 1068–1079.
[23] GELERNTER, N., HERZBERG, A.,
AND LEI-
BOWITZ, H.
Two Cents for Strong Anonymity:
The Anonymous Post-ofﬁce Protocol. Cryptology
ePrint Archive, Report 2016/489, 2016.
http:
//eprint.iacr.org/2016/489.
[24] GILAD, Y., AND HERZBERG, A.
Spying in the
dark: TCP and Tor trafﬁc analysis.
In Interna-
tional Symposium on Privacy Enhancing Technolo-
gies Symposium (2012), Springer, pp. 100–119.
[25] GOLDSCHLAG, D., REED, M., AND SYVERSON,
P. Onion routing. Communications of the ACM 42,
2 (1999), 39–41.
[26] HENRY, R., AND GOLDBERG, I. Thinking inside
the BLAC box: smarter protocols for faster anony-
mous blacklisting. In Proceedings of the 12th ACM
workshop on Workshop on privacy in the electronic
society (2013), ACM, pp. 71–82.
[27] JANSEN, R., AND JOHNSON, A. Safely Measuring
Tor. In Proceedings of the 2016 ACM SIGSAC Con-
ference on Computer and Communications Secu-
rity, Vienna, Austria, October 24-28, 2016 (2016),
pp. 1553–1567.
[28] KESDOGAN, D., EGNER, J., AND BÜSCHKES,
R.
Stop-and-go-mixes providing probabilistic
anonymity in an open system.
In International
Workshop on Information Hiding (1998), Springer,
pp. 83–98.
[29] KWON, A., CORRIGAN-GIBBS, H., DEVADAS,
S., AND FORD, B. Atom: Scalable Anonymity Re-
sistant to Trafﬁc Analysis. CoRR abs/1612.07841
(2016).
[30] KWON, Y. H. Rifﬂe: An efﬁcient communication
system with strong anonymity. PhD thesis, Mas-
sachusetts Institute of Technology, 2015.
[31] LAZAR, D., AND ZELDOVICH, N.
Alpenhorn:
Bootstrapping secure communication without leak-
ing metadata. In Proceedings of the 12th Sympo-
sium on Operating Systems Design and Implemen-
tation (OSDI), Savannah, GA (2016).
[32] LE BLOND, S., CHOFFNES, D., CALDWELL, W.,
DRUSCHEL, P., AND MERRITT, N. Herd: A Scal-
able, Trafﬁc Analysis Resistant Anonymity Net-
work for VoIP Systems.
In ACM SIGCOMM
Computer Communication Review (2015), vol. 45,
ACM, pp. 639–652.
[33] MITZENMACHER, M., AND UPFAL, E.
Proba-
bility and computing: Randomized algorithms and
probabilistic analysis. Cambridge university press,
2005.
[34] MÖLLER, U., COTTRELL, L., PALFRADER, P.,
AND SASSAMAN, L. Mixmaster Protocol-Version
2. Draft.
July, available at:
www. abditum.
com/mixmaster-spec. txt (2003).
[35] PARHI, R., SCHLIEP, M., AND HOPPER, N. MP3:
A More Efﬁcient Private Presence Protocol. arXiv
preprint arXiv:1609.02987 (2016).
[36] SALTZER, J. H., REED, D. P., AND CLARK, D. D.
End-to-end arguments in system design.
ACM
Transactions on Computer Systems (TOCS) 2, 4
(1984), 277–288.
[37] SERJANTOV, A., AND DANEZIS, G. Towards an
information theoretic metric for anonymity. In In-
ternational Workshop on Privacy Enhancing Tech-
nologies (2002), Springer, pp. 41–53.
[38] SERJANTOV, A., DINGLEDINE, R., AND SYVER-
SON, P. From a trickle to a ﬂood: Active attacks
on several mix types. In International Workshop on
Information Hiding (2002), Springer, pp. 36–52.
[39] SERJANTOV, A., AND NEWMAN, R. E. On the
anonymity of timed pool mixes. In Security and
Privacy in the Age of Uncertainty. Springer, 2003,
pp. 427–434.
[40] SHANNON, C. E. A mathematical theory of com-
munication. ACM SIGMOBILE Mobile Computing
and Communications Review 5, 1 (2001), 3–55.
[41] TYAGI, N., GILAD, Y., ZAHARIA, M., AND ZEL-
DOVICH, N.
Stadium: A Distributed Metadata-
Private Messaging System.
Cryptology ePrint
Archive,
Report 2016/943,
2016.
http://
eprint.iacr.org/2016/943.
[42] VAN DEN HOOFF, J., LAZAR, D., ZAHARIA, M.,
AND ZELDOVICH, N. Vuvuzela: Scalable private
messaging resistant to trafﬁc analysis. In Proceed-
ings of the 25th Symposium on Operating Systems
Principles (2015), ACM, pp. 137–152.
[43] WOLINSKY, D. I., CORRIGAN-GIBBS, H., FORD,
B.,
AND JOHNSON, A.
Dissent in numbers:
Making strong anonymity scale. In Presented as
part of the 10th USENIX Symposium on Operat-
ing Systems Design and Implementation (OSDI 12)
(2012), pp. 179–182.
15


---

<!-- Page 16 -->

A
Appendix
A.1
Incremental Computation of the En-
tropy Metric
Let X be a discrete random variable over the ﬁnite set X
with probability mass function p(x) = Pr(X = x). The
Shannon entropy H(X) [40] of a discrete random vari-
able X is deﬁned as
$$
H(X) = -\sum_{x\in\mathcal{X}} p(x)\log p(x). \tag{4}
$$

Let on,k,l be an observation as deﬁned in Section 4.1.3
for a pool at time t. We note that any outgoing message
will have a distribution over being linked with past input
messages, and the entropy Ht of this distribution is our
anonymity metric. Ht can be computed incrementally
given the size of the pool l (from previous mix rounds)
and the entropy Ht−1 of the messages in this previous
pool, and the number of messages k received since a mes-
sage was last sent:
$$
H_t = H\!\left(\left\{\frac{k}{k+l},\,\frac{l}{k+l}\right\}\right)
+ \frac{k}{k+l}\log k + \frac{l}{k+l}H_{t-1}. \tag{5}
$$

for any t > 0 and H0 = 0. Thus for sequential obser-
vations we can incrementally compute the entropy met-
ric for each outgoing message, without remembering the
full history of the arrivals and departures at the Poisson
mix. We use this method to compute the entropy metric
illustrated in Figure 4.
A.2
Proof of Theorem 2
Let us assume, that in mix node Mi there are n′ mes-
sages at a given moment, among which is a target mes-
sage mt. Each message has a delay di drawn from the ex-
ponential distribution with parameter µ. The mix node
generates loops with distribution Pois(λM). The adver-
sary observes an outgoing message m and wants to quan-
tify whether this outgoing message is her target message.
The adversary knows, that the output of the mix node can
be either one of the messages inside the mix or its loop
cover message. Thus, for any message mt, the following
holds
$$
\Pr[m = m_t] = \Pr[m \neq \mathit{loop}]\cdot \Pr[m = m_t \mid m \neq \mathit{loop}]. \tag{6}
$$

We note that the next message m is a loop if and only if
the next loop message is sent before any of the messages
within the mix, i.e., if the sampled time for the next loop
message is smaller than any of the remaining delays of all
messages within the mix. We now leverage the memory-
less property of the exponential distribution to model the
remaining delays of all n′ messages in the mix as fresh
random samples from the same exponential distribution.
$$
\Pr[m \neq \mathit{loop}] = 1-\Pr[m=\mathit{loop}]
= 1-\Pr\!\bigl[X<d_1 \wedge X<d_2 \wedge \cdots \wedge X<d_{n'}\bigr]
= 1-\Pr\!\left[X<\min\{d_1,d_2,\ldots,d_{n'}\}\right]. \tag{7}
$$

We know, that di ∼Exp(µ) for all i ∈{1,...,n′} and
X ∼Exp(λM). Moreover, we know that the minimum
of n independent exponential random variables with rate
µ is an exponential random variable with parameter
∑n′
i µ.
Since all the delays di are independent expo-
nential variables with the same parameter, we have for
Y = min{d1,d2,...dn′}, Y ∼Exp(n′µ). Thus, we obtain
the following continuation of Equation (7).
$$
\begin{aligned}
\Pr[m \neq \mathit{loop}] &= 1-\Pr[X<Y] \\
&= 1-\int_{0}^{\infty} \Pr[X<Y \mid X=x]\Pr[X=x]\,dx \\
&= 1-\int_{0}^{\infty} \Pr[x<Y]\lambda_M e^{-\lambda_M x}\,dx \\
&= 1-\int_{0}^{\infty} e^{-n'\mu x}\lambda_M e^{-\lambda_M x}\,dx \\
&= 1-\frac{\lambda_M}{\lambda_M+n'\mu}
= \frac{n'\mu}{n'\mu+\lambda_M}. \tag{8}
\end{aligned}
$$

Since the probability to send a loop depends only on the
number of messages in a mix, but not on which messages
are in the mix, this probability is independent of the prob-
ability from Theorem 1. Theorem 2 follows directly by
combining Theorem 1 and Equation (8), with n′ = k +l.
We get for messages m1 that previously were in the mix,
Pr[m = m1] = Pr[m ̸= loop]·Pr[m = m1|m ̸= loop]
=
(k +l)µ
(k +l)µ +λM
·
k
n(k +l)
= k
n ·
µ
(k +l)µ +λM
.
Analogously, we get for m2,
Pr[m = m2] = Pr[m ̸= loop]·Pr[m = m2|m ̸= loop]
=
(k +l)µ
(k +l)µ +λM
·
1
k +l
=
µ
(k +l)µ +λM
.
This concludes the proof.
16
