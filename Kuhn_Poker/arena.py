import os
import importlib
import inspect
import itertools
from engine import KuhnEngine

def load_all_bots(directory_name="submissions"):
    bots = []
    current_dir = os.path.dirname(os.path.abspath(__file__))
    target_directory = os.path.join(current_dir, directory_name)
    
    if not os.path.exists(target_directory):
        print(f"Error: Could not find the directory at {target_directory}")
        return bots

    for filename in os.listdir(target_directory):
        if filename.endswith(".py") and filename != "__init__.py":
            module_name = f"{directory_name}.{filename[:-3]}"
            
            # --- THE BULLETPROOF IMPORT BLOCK ---
            try:
                module = importlib.import_module(module_name)
            except Exception as e:
                # If they import 'panel' or have a syntax error, catch it here
                print(f"[DISQUALIFIED] Skipping {filename} due to import error: {e}")
                continue 
            # ------------------------------------

            for name, obj in inspect.getmembers(module, inspect.isclass):
                if hasattr(obj, 'get_action') and name != 'GameState':
                    try:
                        bots.append(obj()) 
                    except Exception as e:
                        print(f"Failed to load class {name} in {filename}: {e}")
    return bots

def run_round_robin():
    bots = load_all_bots()
    if len(bots) < 2:
        print("Need at least 2 bots in the submissions folder to run a tournament.")
        return

    print(f"Loaded {len(bots)} bots. Commencing Round Robin Tournament...\n")
    leaderboard = {bot.name: 0 for bot in bots}
    matches = list(itertools.combinations(bots, 2))
    hands_per_match = 10000

    for b1, b2 in matches:
        p1_profit, p2_profit = 0, 0
        for i in range(hands_per_match):
            # Swap seats to ensure zero-sum fairness
            if i % 2 == 0:
                engine = KuhnEngine(b1, b2)
                res1, res2 = engine.play_hand()
                p1_profit += res1
                p2_profit += res2
            else:
                engine = KuhnEngine(b2, b1)
                res2, res1 = engine.play_hand()
                p2_profit += res2
                p1_profit += res1
                
        leaderboard[b1.name] += p1_profit
        leaderboard[b2.name] += p2_profit
        print(f"Match Complete: {b1.name} ({p1_profit}) vs {b2.name} ({p2_profit})")

    print("\n FINAL LEADERBOARD (Total Net Profit)")
    sorted_board = sorted(leaderboard.items(), key=lambda item: item[1], reverse=True)
    for rank, (name, profit) in enumerate(sorted_board, 1):
        print(f"{rank}. {name}: {profit} chips")

if __name__ == "__main__":
    run_round_robin()