import numpy as np
import pandas as pd
import networkx as nx
from scipy import stats
# plotting
import matplotlib.pyplot as plt

# function definitions
def build_markov(G):
    # Build Markov chain given a weighted network.
    # the number of edges from each source to each target are used to determine the
    # probability of any ship at the given source moving to a next port or staying.
    # returns a dictionary.
    markov = {}
    for port in G.nodes:
        total = 0
        port_markov = {}
        # get the total number of trips observed from each node to each of its targets
        for n in G[port]:
            total += (G[port][n]['weight'])
        # using the total, find the proportion of trips from each port to each target.
        # save it as a dictionary.
        for n in G[port]:
            port_markov[n] = (G[port][n]['weight'] / total)
        # make sure only nodes which have connections to other nodes are added
        if total > 0:
            # add the dictionary for each node to the overarching dict
            markov[port] = port_markov
    return markov

def get_next_markov(start, chain):
    # pass the start_port to the markov dict to access the dictionary holding the markov
    # state information for that port.  Ports visited from this port are the keys, and
    # the proportion of times traveled to each port are the values.
    try:
        # use the markov state information to randomly select a port based on the
        # proportion of past observances
        next = np.random.choice(list(chain[start].keys()),
                                p=list(chain[start].values()))
        return next
    except KeyError:
        # port is a dead end and is not in the chain.  return None
        return None


def build_chains(chain, first_port, target_port, run_target=10000, max_run_multiplier=5, max_iterations=1000):
    first_port = first_port.upper()
    target_port = target_port.upper()
    # target_hop_counter will store how many hops it took to reach the target port in each run
    target_hop_counter = list()
    # run tracker
    run_counter = 0
    # run_target (func argument) is the target for successful runs
    # max_run_multiplier (func argument) is the multiplier of run_targets that will be used to get the max runs
    # max run is the counter for entire loop, including dead ends.  uses max_run_multiplier
    max_runs = run_target * max_run_multiplier
    # max_iterations (func argument) is the number of targets an individual chain will try to build

    while len(target_hop_counter) < run_target:
        # at each round, the starting port needs to be re-set
        start_port = first_port
        # the port chain stores the ports visited in each run
        port_chain = list()
        # start each chain by adding the first port.
        port_chain.append(first_port)
        # use the markov state information to randomly select a port based on the past observances
        next_port = get_next_markov(start_port, chain)

        while next_port != target_port:
            if next_port != None:
                # append that port to the chain
                port_chain.append(next_port)
                # set the next_port as the start_port to continue the chain
                start_port = next_port
            else:
                # next_port == None means there are no ports to travel to, making it a dead end.
                # dead ends will break here, but the run will be counted in the outer loop.
                break
            if len(port_chain) > max_iterations:
                # if max_iterations are exceeded, the chain has expanded beyond a given number of hops.
                # it's unlikely the target port will be reached.
                break
            # use the markov state information to randomly select a port based on the past observances
            next_port = get_next_markov(start_port, markov)

        # only if the next port is the target port, add the length to the counter
        if next_port == target_port:
            target_hop_counter.append(len(port_chain))

        # iterate total runs by 1
        run_counter += 1
        # check if the max run number is exceeded
        if run_counter < max_runs:
            continue
        else:
            break
    print('Length of target_hop_counter:', len(target_hop_counter))
    print('Percent of successful chains:', len(target_hop_counter) / run_counter)
    return target_hop_counter

def analyze_chains(result, first_port, target_port, bin_size=50):
    if len(result) > 0:
        # plot the counts it took to get to the target port
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.hist(result, bins=bin_size)
        plt.title(f"Distribution of {len(result)} runs from {first_port.title()} to {target_port.title()}")
        plt.show()

        print('The mean is', np.mean(result))
        print('The median is', np.median(result))
        print('The mode is', stats.mode(result)[0][0])
    else:
        print(f'No successful chains were built between {first_port.title()} and {target_port.title()}.')


# %% Build the network and markov chain from file
df_edgelist_weighted = pd.read_csv('edgelist_weighted.csv')
G = nx.from_pandas_edgelist(df_edgelist_weighted, source='Source',
                            target='Target', edge_attr=True,
                            create_using=nx.DiGraph)
markov = build_markov(G)

# %% plot network
plt.figure(figsize=(10, 10))
edges = G.edges()
weights = [np.log((G[u][v]['weight']) + .1) for u, v in edges]
pos = nx.spring_layout(G)  # positions for all nodes
# nodes
nx.draw_networkx_nodes(G, pos)
# edges
nx.draw_networkx_edges(G, pos, width=weights)
# labels
nx.draw_networkx_labels(G, pos)
plt.axis('off')
plt.title('Full Network Plot')
plt.show()

# %% calculate and analyze the number of hops between two ports
# assign the port you start chain at and target port
first_port = df_edgelist_weighted['Source'].sample().values[0]
target_port = df_edgelist_weighted['Source'].sample().values[0]

#first_port = 'BOSTON'
#target_port = 'MIAMI'

result = build_chains(markov, first_port, target_port, run_target=10000,
                                 max_run_multiplier=5, max_iterations=500)

analyze_chains(result, first_port, target_port, bin_size=50)
