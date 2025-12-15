# core/route_optimizer.py
"""
TSP (Traveling Salesman Problem) solver for route optimization.
"""

def solve_tsp(distance_matrix: list) -> list:
    """
    Solve TSP problem to find optimal visiting order.
    
    Args:
        distance_matrix: 2D list of distances (in meters or any unit)
                        distance_matrix[i][j] = distance from point i to point j
        
    Returns:
        List of indices representing optimal visit order
        
    Example:
        distance_matrix = [
            [0, 100, 200],
            [100, 0, 150],
            [200, 150, 0]
        ]
        result = solve_tsp(distance_matrix)
        # result might be [0, 1, 2] or [0, 2, 1] depending on which is shorter
    """
    n = len(distance_matrix)
    
    if n == 0:
        return []
    if n == 1:
        return [0]
    if n == 2:
        return [0, 1]
    
    try:
        # Try using OR-Tools (recommended)
        return _solve_with_ortools(distance_matrix)
    except ImportError:
        try:
            # Fallback to python-tsp
            return _solve_with_python_tsp(distance_matrix)
        except ImportError:
            # Last resort: greedy nearest neighbor
            return _solve_greedy(distance_matrix)


def _solve_with_ortools(distance_matrix: list) -> list:
    """Solve TSP using Google OR-Tools."""
    from ortools.constraint_solver import routing_enums_pb2
    from ortools.constraint_solver import pywrapcp
    
    n = len(distance_matrix)
    
    # Create routing index manager
    manager = pywrapcp.RoutingIndexManager(n, 1, 0)  # 1 vehicle, start at 0
    
    # Create routing model
    routing = pywrapcp.RoutingModel(manager)
    
    # Define distance callback
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(distance_matrix[from_node][to_node])
    
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
    # Set search parameters
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = 5  # 5 second limit
    
    # Solve
    solution = routing.SolveWithParameters(search_parameters)
    
    if not solution:
        # Fallback to greedy if no solution found
        return _solve_greedy(distance_matrix)
    
    # Extract route
    route = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        route.append(manager.IndexToNode(index))
        index = solution.Value(routing.NextVar(index))
    
    return route


def _solve_with_python_tsp(distance_matrix: list) -> list:
    """Solve TSP using python-tsp library."""
    import numpy as np
    from python_tsp.exact import solve_tsp_dynamic_programming
    from python_tsp.heuristics import solve_tsp_simulated_annealing
    
    distance_array = np.array(distance_matrix)
    n = len(distance_matrix)
    
    # Use exact solver for small problems (< 20 nodes)
    if n < 20:
        try:
            permutation, distance = solve_tsp_dynamic_programming(distance_array)
            return permutation
        except:
            pass
    
    # Use heuristic for larger problems
    permutation, distance = solve_tsp_simulated_annealing(distance_array)
    return list(permutation)


def _solve_greedy(distance_matrix: list) -> list:
    """
    Greedy nearest neighbor algorithm (fast but not optimal).
    Start at node 0, always go to nearest unvisited node.
    """
    n = len(distance_matrix)
    visited = [False] * n
    route = [0]
    visited[0] = True
    
    current = 0
    
    for _ in range(n - 1):
        nearest_dist = float('inf')
        nearest_node = -1
        
        for j in range(n):
            if not visited[j] and distance_matrix[current][j] < nearest_dist:
                nearest_dist = distance_matrix[current][j]
                nearest_node = j
        
        if nearest_node == -1:
            break
        
        route.append(nearest_node)
        visited[nearest_node] = True
        current = nearest_node
    
    return route
