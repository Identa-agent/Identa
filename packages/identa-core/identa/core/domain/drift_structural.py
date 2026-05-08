import numpy as np
import networkx as nx
from typing import List, Dict, Set, Tuple
from identa.core.domain.structure import AgentStructure

class StructuralDriftAnalyzer:
    def __init__(self, node_insertion_cost: float = 1.0, node_deletion_cost: float = 1.0,
                 edge_insertion_cost: float = 0.5, edge_deletion_cost: float = 0.5):
        self.node_ins = node_insertion_cost
        self.node_del = node_deletion_cost
        self.edge_ins = edge_insertion_cost
        self.edge_del = edge_deletion_cost

    def _to_networkx(self, structure: AgentStructure) -> nx.DiGraph:
        G = nx.DiGraph()
        for node in structure.nodes:
            G.add_node(node.id, type=node.type, weight=node.weight)
        for edge in structure.edges:
            G.add_edge(edge.from_node, edge.to_node)
        return G

    def graph_edit_distance_normalized(self, baseline: AgentStructure, current: AgentStructure) -> float:
        """Normalized GED. For small agent graphs (<50 nodes) this is tractable."""
        G1 = self._to_networkx(baseline)
        G2 = self._to_networkx(current)
        
        # For small graphs, compute exact GED via optimal string alignment approximation
        # For larger graphs, use heuristic
        if len(G1.nodes) <= 20 and len(G2.nodes) <= 20:
            ged = nx.graph_edit_distance(
                G1, G2,
                node_subst_cost=lambda n1, n2: 0 if n1 == n2 else 0.5,
                node_del_cost=lambda n: self.node_del * G1.nodes[n].get('weight', 1.0),
                node_ins_cost=lambda n: self.node_ins * G2.nodes[n].get('weight', 1.0),
                edge_del_cost=lambda e: self.edge_del,
                edge_ins_cost=lambda e: self.edge_ins,
                timeout=5  # seconds
            )
        else:
            # Fallback: use graph similarity via Weisfeiler-Lehman-inspired hashing
            ged = self._approximate_ged(G1, G2)
        
        max_size = max(len(G1.nodes) + len(G1.edges), len(G2.nodes) + len(G2.edges))
        if max_size == 0:
            return 0.0
        return min(ged / max_size, 1.0) if ged else 0.0

    def _approximate_ged(self, G1: nx.DiGraph, G2: nx.DiGraph) -> float:
        """Fast approximation: weighted sum of node/edge Jaccard + degree divergence."""
        nodes1, nodes2 = set(G1.nodes()), set(G2.nodes())
        edges1, edges2 = set(G1.edges()), set(G2.edges())
        
        node_jacc = 1 - len(nodes1 & nodes2) / len(nodes1 | nodes2) if (nodes1 | nodes2) else 0
        edge_jacc = 1 - len(edges1 & edges2) / len(edges1 | edges2) if (edges1 | edges2) else 0
        
        # Degree distribution divergence
        deg1 = sorted([d for n, d in G1.degree()], reverse=True)
        deg2 = sorted([d for n, d in G2.degree()], reverse=True)
        max_len = max(len(deg1), len(deg2))
        deg1 = np.pad(deg1, (0, max_len - len(deg1)))
        deg2 = np.pad(deg2, (0, max_len - len(deg2)))
        degree_dist = np.linalg.norm(deg1 - deg2) / max(np.linalg.norm(deg1), 1e-9)
        
        return (node_jacc * self.node_del * len(nodes1) + 
                edge_jacc * self.edge_del * len(edges1) +
                degree_dist * 0.5)

    def spectral_distance(self, baseline: AgentStructure, current: AgentStructure) -> float:
        """Compare graph Laplacian eigenvalues. Captures topological structure beyond adjacency."""
        G1 = self._to_networkx(baseline)
        G2 = self._to_networkx(current)
        
        if len(G1.nodes) < 2 or len(G2.nodes) < 2:
            return 0.0
        
        # Use normalized Laplacian for directed graphs (use symmetrized version)
        L1 = nx.normalized_laplacian_matrix(G1.to_undirected()).toarray()
        L2 = nx.normalized_laplacian_matrix(G2.to_undirected()).toarray()
        
        eigs1 = np.linalg.eigvalsh(L1)
        eigs2 = np.linalg.eigvalsh(L2)
        
        # Pad to same length
        max_len = max(len(eigs1), len(eigs2))
        eigs1 = np.pad(eigs1, (0, max_len - len(eigs1)))
        eigs2 = np.pad(eigs2, (0, max_len - len(eigs2)))
        
        # Sort and compare
        eigs1, eigs2 = np.sort(eigs1), np.sort(eigs2)
        return np.linalg.norm(eigs1 - eigs2) / np.sqrt(max_len)

    def analyze(self, baseline: AgentStructure, current: AgentStructure) -> Dict[str, float]:
        ged = self.graph_edit_distance_normalized(baseline, current)
        spec = self.spectral_distance(baseline, current)
        
        # Normalize spectral to [0,1] (theoretical max is ~2 for normalized Laplacian)
        spec_norm = min(spec / 2.0, 1.0)
        
        # Ensemble structural score
        score = 0.6 * ged + 0.4 * spec_norm
        
        return {
            "graph_edit_distance": ged,
            "spectral_distance": spec_norm,
            "structural_drift_score": score,
            "is_drift": score > 0.15,  # Threshold based on domain calibration
            "added_nodes": list(set(n.id for n in current.nodes) - set(n.id for n in baseline.nodes)),
            "removed_nodes": list(set(n.id for n in baseline.nodes) - set(n.id for n in current.nodes)),
        }
