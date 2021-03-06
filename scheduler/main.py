#!/usr/bin/env python3
import sys, os
from typing import BinaryIO, Dict, List, NoReturn, Optional, Union
import re
import igraph
import json
import networkx as nx
# import matplotlib.pyplot as plt
from networkx.readwrite import json_graph

class CommunityFinder:
    """
    Class for finding Communities in a given graph.
    It uses the leading eigenvector methods recursively
    to find subcommunities unless we get subcommunities
    with vertices lesser than 3.
    The minimum number of vertices can be specified through
    the constructor or `parse` method.
    """

    def __init__(
        self,
        edge_list_file: Optional[Union[str, BinaryIO]] = None,
        subgraph_min_vertices: int = 3,
        output_format: str = "edgelist",
    ) -> None:
        self._graph: igraph.Graph = None
        self.subgraph_min_vertices = subgraph_min_vertices
        if edge_list_file is not None:
            self.loadFile(edge_list_file)

        self._leaf_communities_edgelist: Dict[str, List[ List[str, str] ] ] = {}
        self._root_communities_edgelist: Dict[str, List[ List[str, str] ] ] = {}
        self.communities_subgraph_inclusive: Dict[str, igraph.Graph] = {}
        self.tree: Dict[str, List[ Dict[str, List[str] ]]] = dict()
        self._property_headings_list : List[str] = [
            "eigen_vector_centrality",
            "betweenness_centrality",
            "closeness_centrality",
            "probability_degree_distribution",
            "clustering_coefficient",
            "neighborhood_connectivity",
            "current_degree",
        ]

        if isinstance(output_format, str) and output_format.lower() in ["edgelist", "json"]:
            self.output_format = output_format
        else:
            self.output_format = "edgelist"

    def set_graph(self, graph: Union[igraph.Graph, nx.Graph]) -> None:
        if not isinstance(graph, igraph.Graph):
            if isinstance(graph, nx.Graph):
                self._graph = igraph.Graph.from_networkx(graph)
                return
            else:
                raise (
                    TypeError,
                    "Graph should be of following types:"
                    " igraph.Graph or networkx.Graph.",
                )
        self._graph = graph

    def get_graph(self) -> igraph.Graph:
        return self._graph

    def parse(self, subgraph_min_vertices=None, key_regulator_bin_width : int = 50 , cf_algo: str = None) -> Dict[str, igraph.Graph]:

        if isinstance(subgraph_min_vertices, int):
            self.subgraph_min_vertices = subgraph_min_vertices
        
        if self._graph is None:
            raise TypeError(
                "Either initialize the class with a edgelist file"
                " or set self.graph explicitly using `.set_graph`."
            )
        elif not isinstance(self._graph, igraph.Graph):
            raise TypeError (
                "Invalid graph type, use `igraph.Graph()`."
            )

        if not isinstance(key_regulator_bin_width,int):
            raise TypeError (
                "Key Regulator bin width should be an integer."
            )

        self._leaf_communities_edgelist.clear()

        _degrees = self._graph.degree()
        _vertex_ids = sorted( range( len(_degrees) ) , key = lambda sub: _degrees[sub])[-key_regulator_bin_width:]
        self._max_degree_nodes : Dict[ str , List[ int ] ] = { self._graph.vs[i]["_nx_name"]:[self._graph.vs[i].degree()] for i in _vertex_ids}

        # A rather unusual data dictionary, containing a dictionary of vertice names as keys
        # a list of just one integer which is that node's degree,
        self._key_reg_trace : Dict[str, str] = { node : "" for node in self._max_degree_nodes.keys() }

        self.tree['root'] = {
            'name' : 'root',
            'lineage' : '0',
            'current_depth': 0,
            'has_keyreg' : False,
            'num_vertices' : 0,
            'is_leaf_node' : False,
            'children': [],
            'key_regs' : [],
            'cf_algo' : '',
            'output_format' : self.output_format,
            'subgraph_min_vertices' : self.subgraph_min_vertices,
            'key_regulator_bin_width' : key_regulator_bin_width,
        }

        self.key_regulators = self._max_degree_nodes.copy()
        
        if cf_algo is not None and isinstance(cf_algo, str):
            self.cf_algo = cf_algo # This maybe used somewhere in the class so lets make it a class variable.
            if cf_algo == 'louvain':
                self.tree['root']['cf_algo'] = 'Louvain'
                sys.stdout.write(f"\nUsing the faster Louvain's method (a.k.a community_multilevel).\n")
                self.find_communities_recursive(self._graph, tree = self.tree['root'], method=0)
            elif cf_algo == 'leading_eigenvector':
                self.tree['root']['cf_algo'] = 'Leading eigenvector'
                sys.stdout.write(f"\nUsing the leading eigenvector method since |V|.")
                self.find_communities_recursive(self._graph, tree = self.tree['root'], method=1)
            else:
                raise ValueError(f"Invalid community finding algorithm {cf_algo}.")
        else:
            sys.stdout.write(f"\n\nUsing the leading louvian method since no algo is defined.")
            self.find_communities_recursive(self._graph, tree = self.tree['root'], method=0)

        l = self.communities_subgraph_inclusive

        # Edgelist not required.
        _merged_dict = self._root_communities_edgelist.copy()
        _merged_dict.update(self._leaf_communities_edgelist)

        self.tree['root']['key_reg_trace'] = self._key_reg_trace.copy()
        
        return self._leaf_communities_edgelist

    def has_cycles(self, graph: igraph.Graph):
        if isinstance(graph, igraph.Graph):
            graph = nx.Graph(graph.get_edgelist())
        try:
            nx.find_cycle(graph)
            return True
        except nx.NetworkXNoCycle:
            return False
    
    def check_star_topology(self, graph: igraph.Graph):

        _vs_count = len(graph.vs)
        _es_count = len(graph.vs)

        # Number of edges should be equal
        # to (Number of vertices - 1)
        if _es_count != ( _vs_count - 1):
            return False
    
        # a single node is termed as a bus topology
        if (_vs_count == 1):
            return True
    
        vertex_degrees = graph.degree()
    
        # countCentralNodes stores the count of nodes
        # with degree V - 1, which should be equal to 1
        # in case of star topology
        # countCentralNodes = 0
        # centralNode = 0
    
        central_nodes = [ 1 if degree == _vs_count-1 else 0 for degree in vertex_degrees]

        # there should be only one central node
        # in the star topology
        if (sum(central_nodes) != 1):
            return False
    
        # for i in range(1, V + 1):
        #     # except for the central node
        #     # check if all other nodes have
        #     # degree 1, if not return false
        #     if (i == centralNode):
        #         continue
        #     if (vertexDegree[i] != 1):
        #         return False
    
        # if all three necessary
        # conditions as discussed,
        # satisfy return true
        return True

    def find_communities_recursive(self, graph: igraph.Graph, depth: Union[str, None] = None, tree = None, method : int = 0) -> None:

        if depth is not None:
            self.communities_subgraph_inclusive[depth] = graph.copy()
        
        # Tree setting spot.
        _key_reg_vertex = [ [ i.index,i["_nx_name"] ] for i in graph.vs if i["_nx_name"] in self.key_regulators.keys()]

        for _, name in _key_reg_vertex:
            # This will capture the maximum depth for each keyreg in time.
            self._key_reg_trace[name] = depth

        has_keyreg = True if len(_key_reg_vertex) > 0 else False

        l = dict()


        mathematical_properties = self.find_topological_and_centrality_properties(
            graph,
            [ i[0] for i in _key_reg_vertex ],
        )
        
        for vertex_id, vertex_name in _key_reg_vertex:
            l[vertex_name] = dict()
            _index = 0
            for value in mathematical_properties[vertex_id]:
                l[vertex_name][self._property_headings_list[_index]] = value
                _index += 1

        tree['lineage'] = '0' if depth is None else depth
        tree['current_depth'] = tree['lineage'].count('_') + 1
        tree['key_regs'] = l
        tree['num_vertices'] = len(graph.vs)
        tree['has_keyreg'] = has_keyreg
        tree['name'] = 'root' if depth is None else depth.split('_')[-1]
        

        # Implement motif discovery here.
        if not self.has_cycles(graph):
            tree['is_leaf_node'] = True
            return

        if len(graph.vs) <= self.subgraph_min_vertices:
            _edg_list = [ [ graph.vs[edge]["_nx_name"] for edge in line] for line in graph.get_edgelist() ]
            if len(_edg_list) > 1:
                self._leaf_communities_edgelist[depth] = _edg_list
                tree['is_leaf_node'] = True
            return

        if depth is not None:
            _edg_list = [ [ graph.vs[edge]["_nx_name"] for edge in line] for line in graph.get_edgelist() ]
            self._root_communities_edgelist[f"0_{depth}"] = _edg_list

        if method == 1:
            # print("Using leading eigenvector method.", flush=True)
            communities = list(graph.community_leading_eigenvector( ))
        elif method == 0:
            # print("Using Louvain's method.", flush=True)
            communities = list(graph.community_multilevel())

        for vertices in communities:
            if len(vertices) == len(graph.vs):communities.remove(vertices)

        for cg_index, community_vertices in enumerate(communities,1):
            # Tree Stuff
            _c_tree = {
                'name' : None,
                'lineage' : None,
                'current_depth' : None,
                'children': [],
                'key_regs' : {},
            }

            sub_graph = graph.subgraph( graph.vs.select(community_vertices) )

            if depth is None:
                _depth = str(cg_index)
            else:
                _depth = f"{depth}_{str(cg_index)}"

            self.find_communities_recursive(sub_graph, tree = _c_tree,  depth = _depth, method = method)
            # Tree Stuff.
            tree['children'].append(_c_tree)

    def find_topological_and_centrality_properties(self, graph: igraph.Graph , vertex_indices: List[int] ) -> Dict [int, List[float]]:
        """
        Finds the topological and centrality properties of a vertex.
        """
        _output: Dict[int, List[float]] = dict()
        
        vertice_count = len(graph.vs)
        
        if vertice_count < 3:
            for index in vertex_indices:
                _output[index] = [-1,-1,-1,-1,-1,-1,-1]
            return _output

        

        # See: https://igraph.org/python/doc/api/igraph._igraph.GraphBase.html#eigenvector_centrality
        _eigen_vector_centrality = graph.evcent()

        # See: https://igraph.org/python/doc/api/igraph._igraph.GraphBase.html#betweenness
        # Also see: https://en.wikipedia.org/wiki/Betweenness_centrality#Definition
        # The value is scaled by dividing the centrality value by total number of vertex pairs in the graph.
        _betweenness_centrality_arr = graph.betweenness()


        # See: https://igraph.org/python/doc/api/igraph._igraph.GraphBase.html#closeness
        _closeness_centrality = graph.closeness()

        # We find the degree of current node then find the number
        # of occurrences of that degree in the list of degrees of all nodes.
        # Then we divide the above number with the length of all distinct degrees
        # present in the graph.
        _degrees = graph.degree()


        # See: https://igraph.org/python/doc/api/igraph._igraph.GraphBase.html#transitivity_local_undirected
        _clustering_coeff = graph.transitivity_local_undirected()

        # See: https://www.centiserver.org/centrality/Neighborhood_Connectivity/


        for vertex_index in vertex_indices:
            _neighborhood = graph.neighbors(vertex_index)
            
            _output[vertex_index] = [
                _eigen_vector_centrality[vertex_index]/( ( (vertice_count-1)*(vertice_count-2) ) / 2 ), # Eigenvector Centrality
                _betweenness_centrality_arr[vertex_index] / ( ( (vertice_count-1)*(vertice_count-2) ) / 2 ), # Betweenness Centrality
                _closeness_centrality[vertex_index], # Closeness Centrality
                _degrees.count( _degrees[vertex_index] ) / len(_degrees), # Probability Degree Distribution
                _clustering_coeff[vertex_index], # Clustering Coefficient
                sum([graph.vs[vid].degree() for vid in _neighborhood ])/len(_neighborhood), # Neighborhood Connectivity
                _degrees[vertex_index], # Degree at this level.
            ]
        
        return _output

    def loadFile(self, filePath: Union[str, BinaryIO]) -> None:
        # TODO:
        # Add support for multiple format of network input e.g. json etc.
        # Add a checking parameter to check if the file is a valid network file.
        try:
            format = filePath.split('.')[-1]
            if format == 'json':
                print("Loading network from json file is not yet supported.", flush=True)
                raise NotImplementedError
            elif format == 'csv' or format == 'tsv':
                with open(filePath, 'r') as f:
                    text = f.read()
                    tsv_l = len(re.findall(r'.*?\t.*\s{1}', text))
                    csv_l = len(re.findall(r'.*?,.*\s{1}', text))

                    if tsv_l > csv_l:
                        print("Loading network from tsv file.")
                        self._graph = nx.read_edgelist(filePath, comments="#" , delimiter="\t")
                    else:
                        print("Loading network from csv file.")
                        self._graph = nx.read_edgelist(filePath, comments="#" , delimiter=",")
            else:
                print("Unknown file format.")
                raise Exception("Unknown file format.")
            # _json_data = json.dumps(json_graph.node_link_data(self._graph))
            # _json_file_obj = open( os.path.join("", f"parent_network.json"), "w")
            # _json_file_obj.write(_json_data)
            # _json_file_obj.flush()
            # _json_file_obj.close()
            self._graph = igraph.Graph.from_networkx(self._graph)

        except IOError:
            sys.stderr.write(
                "Error while reading the file," " no such file or directory."
            )
            raise

    def genrate_edgelist(self, v_name_type: str = '_nx_name'):
        if self._leaf_communities_edgelist == {}:
            self.parse()
        for order, subgraph in self._leaf_communities_edgelist.items():
            l = self._graph.vs[0]
            yield order, [ [self._graph.vs[edge][v_name_type] for edge in line] for line in subgraph.get_edgelist() ]

    def write_leaf_networks(self, base_dir : str = "./", format: str = None ) -> None:
        # If no output type is specified then fallback to class default.
        if format is None:format = self.output_format

        _dir = os.path.join(base_dir, "leaf_networks")
    
        if not os.path.exists(_dir):os.makedirs(_dir)
        
        # JSON will always be rendered anyways as it's use for displaying the interactive subgraphs.
        for filename, sub_graph_edgelist in self._leaf_communities_edgelist.items():
            g_sub = nx.Graph(sub_graph_edgelist)
            json_data = json.dumps(json_graph.node_link_data(g_sub))
            __dir = os.path.join(_dir, "leaf_nodes_json")
            
            try:
                os.mkdir(__dir)
            except FileExistsError:
                pass

            json_file_obj = open(os.path.join(__dir,f"{filename}.json"),"w")
            json_file_obj.write(json_data)
            json_file_obj.flush()
            json_file_obj.close()
        
        if format == "edgelist":
            __dir = os.path.join(_dir, "leaf_nodes_edgelist")
                
            try:os.mkdir(__dir)
            except FileExistsError:pass

            for filename, sub_graph_edgelist in self._leaf_communities_edgelist.items():
                with open(os.path.join(__dir,f"{filename}.tsv"),"w") as f:
                    for line in sub_graph_edgelist:
                        f.write(f"{line[0]}\t{line[1]}\n")


        for filename, sub_graph_edgelist in self._leaf_communities_edgelist.items():
            
            __dir = os.path.join(_dir, "leaf_nodes_svg_render")
            
            try:os.mkdir(__dir)
            except FileExistsError:pass

            svg_file_name  = os.path.join(__dir,f"{filename}.svg")
            # self.communities_subgraph_inclusive[filename][0]["shape"] = 3
            self.communities_subgraph_inclusive[filename].write_svg(
                svg_file_name,
                labels="_nx_name",
                width=400,
                colors="lightblue",
                height=400,
                vertex_size=50,
                layout=igraph.Graph.layout_lgl(self.communities_subgraph_inclusive[filename]),
            )
    
    def write_subgraphs(self, base_dir : str , format : str = 'edgelist') -> None:
        # If no output type is specified then fallback to class default.
        if format is None:format = self.output_format

        _base_dir = os.path.join(base_dir, "subgraphs")

        try:
            os.mkdir(_base_dir)
        except FileExistsError:
            pass

        _prop_plot__dir = os.path.join(_base_dir, "prop_plots")
            
        try:
            os.mkdir(_prop_plot__dir)
        except FileExistsError:
            pass
        
        # Add root node as well.
        self.communities_subgraph_inclusive['0'] = self._graph

        for _depth in self.communities_subgraph_inclusive.keys():
            graph = self.communities_subgraph_inclusive[_depth]

            vertice_count = len(graph.vs)
            
            if vertice_count < 3:
                # Figure this one out.
                continue
                # return (-1,-1,-1,-1,-1,-1)

            _degrees = graph.degree()


            _eigen_vector_centrality = [ i/(((vertice_count-1)*(vertice_count-2))/2) for i in graph.evcent()]
            _eigen_vector_centrality = sorted ( [ [i,j] for i,j in zip(_degrees , _eigen_vector_centrality) ] , key = lambda x:x[0] , reverse = False)

            _betweenness_centrality = [ i / ( ( (vertice_count-1)*(vertice_count-2) ) / 2 ) for i in graph.betweenness() ]
            _betweenness_centrality = sorted ( [ [i,j] for i,j in zip(_degrees , _betweenness_centrality) ] , key = lambda x:x[0] , reverse = False)

            _closeness_centrality = graph.closeness()
            _closeness_centrality = sorted ( [ [i,j] for i,j in zip(_degrees , _closeness_centrality) ] , key = lambda x:x[0] , reverse = False)

            
            _p_degree_distribution = [ _degrees.count(i) / vertice_count for i in _degrees]
            _p_degree_distribution = sorted ( [ [i,j] for i,j in zip(_degrees , _p_degree_distribution) ] , key = lambda x:x[0] , reverse = False)

            _clustering_coeff = graph.transitivity_local_undirected()
            _clustering_coeff = sorted ( [ [i,j] for i,j in zip(_degrees , _clustering_coeff) ] , key = lambda x:x[0] , reverse = False)

            _neighborhood_connectivity = []
            for vertex in graph.vs():
                vid = vertex.index
                neighbors = graph.neighbors(vid)
                if len(neighbors) == 0:
                    _neighborhood_connectivity.append(0)
                    continue
                _neighborhood_connectivity.append(sum( [graph.vs[_vid].degree() for _vid in neighbors ])/len(neighbors))
            _neighborhood_connectivity = sorted ( [ [i,j] for i,j in zip(_degrees , _neighborhood_connectivity) ] , key = lambda x:x[0] , reverse = False)
            

            _prop_list = [
                _eigen_vector_centrality,
                _betweenness_centrality,
                _closeness_centrality,
                _p_degree_distribution,
                _clustering_coeff,
                _neighborhood_connectivity
            ]

            

            for i in range(len(_prop_list)):
                property_name = self._property_headings_list[i]
                x_property_values = [x for x,_ in _prop_list[i]]
                y_property_values = [y for _,y in _prop_list[i]]

                l = '\n'.join(
                    [
                        f"{x_property_values[i]},{y_property_values[i]}" for i in range(len(x_property_values))
                    ]
                )

                l = "index,value\n" + l

                with open(
                    os.path.join(_prop_plot__dir,f"{_depth}-{property_name}.csv"),
                    "w"
                    ) as f:
                    f.write(l)

        if format == 'edgelist':
            for _depth in self.communities_subgraph_inclusive.keys():
                __dir = os.path.join(_base_dir, "subgraphs_tsv")
                try:os.mkdir(__dir)
                except FileExistsError:pass
                _sg_edgelist = [ [  self.communities_subgraph_inclusive[_depth].vs[edge]['_nx_name'] for edge in line ] for line in self.communities_subgraph_inclusive[_depth].get_edgelist() ] 
                with open(os.path.join(__dir,f"{_depth}.tsv"), "w") as f:
                    for line in _sg_edgelist:
                        f.write(f"{line[0]}\t{line[1]}\n")

        # JSON will always be rendered as it's use for displaying the interactive subgraphs.
        for _depth in self.communities_subgraph_inclusive.keys():
            g_sub = nx.Graph( [ [ self.communities_subgraph_inclusive[_depth].vs[edge]['_nx_name'] for edge in pair ] for pair in  self.communities_subgraph_inclusive[_depth].get_edgelist()] )
            json_data = json.dumps(json_graph.node_link_data(g_sub))
            __dir = os.path.join(_base_dir, "subgraphs_json")
            
            try:
                os.mkdir(__dir)
            except FileExistsError:
                pass

            json_file_obj = open(
                os.path.join(__dir,f"{_depth}.json"),
                "w"
            )
            json_file_obj.write(json_data)
            json_file_obj.flush()
            json_file_obj.close()

        # SVG will always be rendered.
        for _depth in self.communities_subgraph_inclusive.keys():
            
            __dir = os.path.join(_base_dir, "subgraphs_svg_render")
            
            try:os.mkdir(__dir)
            except FileExistsError:pass

            svg_file_name  = os.path.join(__dir, f'{_depth}.svg')
            _l = len(self.communities_subgraph_inclusive[_depth].vs)
            dim = 30 * _l

            colors = [ "lightblue" if i['_nx_name'] in self.key_regulators.keys() else "lightsalmon" for i in self.communities_subgraph_inclusive[_depth].vs]

            self.communities_subgraph_inclusive[_depth].write_svg(
                svg_file_name,
                labels="_nx_name",
                width= dim if dim > 400 else 90 * _l,
                colors=colors,
                height= dim if dim > 400 else 90 * _l,
                vertex_size=40,
                layout=igraph.Graph.layout_lgl(self.communities_subgraph_inclusive[_depth]),
            )

if __name__ == "__main__":
    # The input to this script are: 
    # network file , cf method , V(min) , number of key regs to trace , output file format , dir to write output to.
    # cf_method => [louvain, leading_eigenvector]
    if len(sys.argv) < 3:
        sys.stderr.write("Please provide filepath as first commandline arg and a directory to write the edgelist.")

        cf = CommunityFinder("/var/www/html/scheduler/test_data.tsv")#sys.argv[1])

        leaf_communities = cf.parse()
        
        lc = cf._leaf_communities_edgelist

        tree__ = cf.tree['root']

        key_regs = cf.key_regulators

        with open("lib/knowledge_tree_1.json", "w") as fp:
            json.dump(tree__,fp , indent=4 , skipkeys=True)

        community_subgraph_inclusive = cf.communities_subgraph_inclusive

        # cf.write_leaf_networks(base_dir="./tmp")

        cf.write_subgraphs(base_dir="./tmp")


        key_regs.clear()
    else:
        output_dir = sys.argv[2]
        # TODO:
        # - add a check to see if the output directory exists.
        # - add safety nets for arguments so no bogus args get into the class.
        with open(f"{output_dir.rstrip('/')}/arguments.txt", "r") as fp:
            cf_args = fp.read().split("\n")

        if 'output-type-edgelist-tsv' in cf_args[3]:format = 'edgelist'
        elif 'output-type-json' in cf_args[3]:format = 'json'
        else:format = ''

        cf = CommunityFinder(sys.argv[1], output_format=format,)

        leaf_communities = cf.parse(
            subgraph_min_vertices=int(cf_args[1]),
            key_regulator_bin_width=int(cf_args[2]),
            cf_algo=cf_args[0],
            )

        lc = cf._leaf_communities_edgelist

        community_subgraph_inclusive = cf.communities_subgraph_inclusive

        tree__ = cf.tree['root']

        with open(f"{output_dir.rstrip('/')}/tree.json", "w") as fp:
            json.dump(tree__,fp)


        cf.write_leaf_networks(base_dir=output_dir , format= format)

        cf.write_subgraphs(base_dir=output_dir , format= format)

