"""
Ground-truth seed → level-order pairs collected from in-game runs.

Indices reference RUSH_LEVELS[rush_key] from rush_data.py:
  red:    0=Elevate Traversal I, 1=Elevate Traversal II, 2=Purify Traversal,
          3=Godspeed Traversal, 4=Stomp Traversal, 5=Fireball Traversal,
          6=Dominion Traversal, 7=Book of Life Traversal
  violet: 0=Doghouse, 1=Choker, 2=Chain, 3=Hellevator, 4=Razor,
          5=All Seeing Eye, 6=Resident Saw I, 7=Resident Saw II
  yellow: 0=Sunset Flip Powerbomb, 1=Balloon Mountain, 2=Climbing Gym,
          3=Fisherman Suplex, 4=STF, 5=Arena, 6=Attitude Adjustment, 7=Rocket
"""

GROUND_TRUTH = [
    # (rush_key, seed, expected_order_as_indices_into_RUSH_LEVELS[rush_key])
    ("red", 54304,  [4, 6, 3, 1, 5, 2, 0, 7]),  # Stomp,Dominion,Godspeed,ElevII,Fireball,Purify,ElevI,BookOfLife
    ("red", 5189,   [3, 5, 6, 4, 7, 0, 1, 2]),  # Godspeed,Fireball,Dominion,Stomp,BookOfLife,ElevI,ElevII,Purify
    ("red", 2222,   [4, 2, 5, 3, 1, 7, 0, 6]),  # Stomp,Purify,Fireball,Godspeed,ElevII,BookOfLife,ElevI,Dominion
    ("red", 4444,   [1, 5, 3, 2, 4, 6, 0, 7]),  # ElevII,Fireball,Godspeed,Purify,Stomp,Dominion,ElevI,BookOfLife
    ("red", 123456, [0, 4, 3, 7, 6, 1, 2, 5]),  # ElevI,Stomp,Godspeed,BookOfLife,Dominion,ElevII,Purify,Fireball
]
