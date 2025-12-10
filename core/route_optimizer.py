# core/route_optimizer.py
from typing import List
from ortools.constraint_solver import pywrapcp, routing_enums_pb2


def solve_tsp(distance_matrix: List[List[float]], time_limit_seconds: int = 5) -> List[int]:
    """
    Solve a TSP (Traveling Salesman Problem) using OR-Tools.
    
    Args:
        distance_matrix: 2D list where distance_matrix[i][j] = distance from node i to j (in meters)
        time_limit_seconds: Maximum time to spend optimizing (default: 5 seconds)
    
    Returns:
        List of node indices in optimized visiting order, e.g. [0, 3, 1, 2]
        Node 0 is treated as the depot/starting point.
    
    Note:
        - For n <= 1, returns the trivial order
        - If solver fails, returns original order as fallback
    """
    n = len(distance_matrix)
    
    # ✅ Edge case: empty or single node
    if n <= 1:
        return list(range(n))
    
    # ✅ Edge case: validate matrix dimensions
    if any(len(row) != n for row in distance_matrix):
        raise ValueError(f"Distance matrix must be square, got {n}x{[len(row) for row in distance_matrix]}")

    # Create routing index manager: n nodes, 1 vehicle, depot at index 0
    manager = pywrapcp.RoutingIndexManager(n, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    # Distance callback
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        # ✅ Add bounds checking
        if from_node >= n or to_node >= n:
            return 0
        return int(distance_matrix[from_node][to_node])

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Search parameters
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = time_limit_seconds

    # ✅ Add logging for debugging (optional)
    # search_parameters.log_search = True

    # Solve
    solution = routing.SolveWithParameters(search_parameters)

    if not solution:
        # ✅ Better logging
        print(f"⚠️ TSP solver failed for {n} nodes, using original order")
        return list(range(n))

    # Extract solution
    index = routing.Start(0)
    order = []
    visited = set()  # ✅ Detect infinite loops
    
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        if node in visited:  # ✅ Safety check
            print(f"⚠️ TSP solution has cycle at node {node}")
            break
        visited.add(node)
        order.append(node)
        index = solution.Value(routing.NextVar(index))

    # ✅ Verify we got all nodes
    if len(order) != n:
        print(f"⚠️ TSP solution incomplete: got {len(order)} nodes, expected {n}")
        return list(range(n))

    return order


def solve_tsp_with_stats(distance_matrix: List[List[float]]) -> tuple[List[int], dict]:
    """
    Solve TSP and return solution with statistics.
    
    Returns:
        (order, stats) where stats contains:
        - total_distance: Total route distance
        - solving_time: Time spent solving
        - num_nodes: Number of nodes
    """
    import time
    
    start_time = time.time()
    order = solve_tsp(distance_matrix)
    solving_time = time.time() - start_time
    
    # Calculate total distance
    total_distance = 0.0
    n = len(order)
    for i in range(n - 1):
        from_node = order[i]
        to_node = order[i + 1]
        total_distance += distance_matrix[from_node][to_node]
    
    stats = {
        "total_distance": total_distance,
        "solving_time": solving_time,
        "num_nodes": n,
    }
    
    return order, stats
