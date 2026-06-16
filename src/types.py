# Define data types for recipe attributes
Recipe = namedtuple("Recipe", ["name", "description"])
Meal = namedtuple("Meal", ["ingredients", "instructions"])
