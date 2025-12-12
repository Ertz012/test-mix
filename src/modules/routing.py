import random

class Routing:
    def __init__(self, config, network_map):
        self.config = config
        self.network_map = network_map
        self.nodes_per_layer = self.config['topology']['nodes_per_layer']
        
        # Categorize nodes
        self.entries = [n for n in network_map if n.startswith('e')]
        self.intermediates = [n for n in network_map if n.startswith('i')]
        self.exits = [n for n in network_map if n.startswith('x')]
        
        # Sort for deterministic testing if needed
        self.entries.sort()
        self.intermediates.sort()
        self.exits.sort()

    def get_path(self, src, dst, exclude_nodes=None):
        """
        Generates a stratified path: Sender -> Entry -> Intermediate -> Exit -> Receiver
        Optionally excludes specific nodes (e.g. for re-establishment around failures).
        """
        if exclude_nodes is None:
            exclude_nodes = []
            
        # Filter available nodes
        avail_entries = [n for n in self.entries if n not in exclude_nodes]
        avail_inters = [n for n in self.intermediates if n not in exclude_nodes]
        avail_exits = [n for n in self.exits if n not in exclude_nodes]
        
        # Fallback if exclusion leads to empty layers
        if not avail_entries: avail_entries = self.entries
        if not avail_inters: avail_inters = self.intermediates
        if not avail_exits: avail_exits = self.exits

        # Select one random node from each layer
        entry_node = random.choice(avail_entries)
        inter_node = random.choice(avail_inters)
        exit_node = random.choice(avail_exits)
        
        # Full route: src (implicitly known) -> Entry -> Inter -> Exit -> dst
        route = [entry_node, inter_node, exit_node, dst]
        return route

    def get_disjoint_paths(self, src, dst, k=2):
        """
        Naive disjoint path generation. 
        Tries to find k paths that don't share nodes (except src/dst).
        """
        paths = []
        used_nodes = set()
        
        for _ in range(k):
            avail_entries = [n for n in self.entries if n not in used_nodes]
            avail_inters = [n for n in self.intermediates if n not in used_nodes]
            avail_exits = [n for n in self.exits if n not in used_nodes]
            
            if not (avail_entries and avail_inters and avail_exits):
                break
                
            e = random.choice(avail_entries)
            i = random.choice(avail_inters)
            x = random.choice(avail_exits)
            
            paths.append([e, i, x, dst])
            used_nodes.update([e, i, x])
            
        return paths
