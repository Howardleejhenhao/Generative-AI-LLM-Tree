def resolve_node_position_inputs(*, position_x, position_y) -> tuple[int, int]:
    try:
        resolved_x = int(position_x)
        resolved_y = int(position_y)
    except (TypeError, ValueError) as exc:
        raise ValueError("Valid position_x and position_y are required.") from exc

    if resolved_x < 0 or resolved_y < 0:
        raise ValueError("Node position must be non-negative.")

    return resolved_x, resolved_y
