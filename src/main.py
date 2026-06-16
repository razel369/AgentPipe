from backend import Recipe
from data import fetch_recipe

def create_meal(name: str, description: str) -> Recipe:
    meal = Recipe(name, description)
    fetch_recipe(meal.name)
    return meal
