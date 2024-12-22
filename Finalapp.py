import streamlit as st
import sys
import os
from typing import List, Dict, Optional
from crewai import Agent, Task, Crew, Process, LLM
import json
import logging
import sqlite3

# Configure logging
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set your Groq API key directly here
GROQ_API_KEY = "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"  # Replace with your actual API key


# User tracking functions
def init_user_db():
	conn = sqlite3.connect("user_data.db")
	cursor = conn.cursor()
	cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY
        )
    """)
	conn.commit()
	return conn


def add_user(conn, email):
	cursor = conn.cursor()
	try:
		cursor.execute("INSERT INTO users (email) VALUES (?)", (email,))
		conn.commit()
		return True  # New user added
	except sqlite3.IntegrityError:
		return False  # User already exists


def get_user_count(conn):
	cursor = conn.cursor()
	cursor.execute("SELECT COUNT(*) FROM users")
	count = cursor.fetchone()[0]
	return count


class RecipeGenerationSystem:
	def __init__(self):
		"""Initialize the Recipe Generation System"""
		self.llm = LLM(
			model="groq/llama3-70b-8192",
			temperature=0.8,
			api_key=GROQ_API_KEY
		)

	def create_agents(self) -> Dict[str, Agent]:
		"""Create specialized agents for recipe generation"""

		recipe_creator = Agent(
			role="Recipe Creator",
			goal="""Design low calorie and high protein recipes using the ingredients from the ingredients list 
            that taste good """,
			backstory=""" Former overweight individual turned nutrionist and expert chef, now helping his clients 
            shed pounds while building muscle""",
			llm=self.llm,
			verbose=True
		)

		nutrition_expert = Agent(
			role="Nutrition Expert",
			goal="Analyze recipe nutrition",
			backstory="Certified nutritionist with recipe analysis expertise",
			llm=self.llm,
			verbose=True
		)

		return {
			"creator": recipe_creator,
			"nutrition": nutrition_expert
		}

	def create_tasks(self, ingredients: List[str], calories: int,
					 dietary_restrictions: List[str], cooking_time: int,
					 skill_level: str, agents: Dict[str, Agent]) -> List[Task]:
		"""Create tasks for recipe generation process"""

		recipe_creation_task = Task(
			description=f"""Create 2 different detailed low calorie and high protein recipe options with these requirements:
            Ingredients available: {', '.join(ingredients)}
            Maximum calories: {calories}
            Dietary restrictions: {', '.join(dietary_restrictions) if dietary_restrictions else 'None'}
            Maximum cooking time: {cooking_time} minutes
            Skill level: {skill_level}

            NOTE- The Maximum calorie limit ({calories}) and Maximum cooking time ({cooking_time}) is for each recipe option. 
            The 2 recipes combined can exceed the calorie and time limit.



            You don't have to use each ingredient and can use 1-2 extra ingredients if necessary, ensuring they are
			simple and accessible

            Provide each recipe in this format:
            # [Recipe Name]

            ## Description
            [Brief description of the dish]

            ## Ingredients with quantity for 1 serving 
            - [Ingredient 1 with quantity]
            - [Ingredient 2 with quantity]
            [etc.]

            ## Instructions
            1. [Step 1]
            2. [Step 2]
            [etc.]

            ## Cooking Time
            - Preparation: [X] minutes
            - Cooking: [Y] minutes
            - Total Time: [Z] minutes

            """,
			expected_output="A detailed recipe in the specified format",
			agent=agents["creator"]
		)

		nutrition_analysis_task = Task(
			description=f"""Analyze the nutritional content of each of the recipes above.
            Maximum allowed calories: {calories} per serving

            Provide the analysis in this format:
            ## Nutritional Information (per serving)

            - Calories: [X] kcal
            - Protein: [X]g
            - Carbohydrates: [X]g
            - Fat: [X]g
            - Fiber: [X]g
            - Sodium: [X]mg

            ## Additional Notes
            [Any relevant nutritional notes or warnings based on dietary restrictions]

            NOTE - The nutrition analysis for each recipe will be displayed with the recipe itself. 
            """,
			expected_output="A detailed nutritional analysis in the specified format",
			agent=agents["nutrition"]

		)

		return [recipe_creation_task, nutrition_analysis_task]

	def generate_recipe(self, ingredients: List[str], calories: int,
						dietary_restrictions: List[str], cooking_time: int,
						skill_level: str) -> Dict:
		"""Generate recipe with all components"""
		try:
			agents = self.create_agents()
			tasks = self.create_tasks(ingredients, calories, dietary_restrictions,
									  cooking_time, skill_level, agents)

			crew = Crew(
				agents=list(agents.values()),
				tasks=tasks,
				verbose=True,
				process=Process.sequential
			)

			# Execute the tasks and handle results
			result = crew.kickoff()
			print(result)
			print(str(tasks[0].output))

			# Extract results directly from task outputs
			print(result.raw)
			return {"recipe": str(tasks[0].output), "nutrition": result.raw}

		except Exception as e:
			logger.error(f"Error in recipe generation: {str(e)}")
			raise


def main():
	st.set_page_config(
		page_title="NutriFit AI",
		page_icon="🥗",
		layout="wide"
	)

	st.title("🥗 NutriFit AI")
	st.write("Generate personalized, healthy recipes using AI!")
	# st.image("C:\Users\91822\OneDrive\Desktop\stimage.png", use_container_width=True)

	# Initialize user tracking database
	conn = init_user_db()

	# Sidebar inputs
	with st.sidebar:
		st.header("User Sign-up")
		email = st.text_input("Enter your email to register or sign in:")

		if st.button("Submit Email"):
			if email:
				if add_user(conn, email):
					st.success("Thank you for signing up!")
				else:
					st.info("You are already registered.")
			else:
				st.error("Please enter a valid email.")

		st.header("Recipe Parameters")

		ingredients_input = st.text_area(
			"Enter ingredients (one per line)",
			placeholder="Example:\ntomatoes\nchicken\nrice",
			height=150
		)
		ingredients = [ing.strip() for ing in ingredients_input.split('\n') if ing.strip()]

		col1, col2 = st.columns(2)
		with col1:
			calories = st.number_input(
				"Max calories",
				min_value=100,
				max_value=2000,
				value=500,
				step=50
			)

			skill_level = st.selectbox(
				"Cooking skill level",
				["Beginner", "Intermediate", "Advanced"],
				index=1
			)

		with col2:
			cooking_time = st.number_input(
				"Max cooking time (min)",
				min_value=15,
				max_value=120,
				value=30,
				step=15
			)

		dietary_restrictions = st.multiselect(
			"Dietary Restrictions",
			["Vegetarian", "Vegan", "Gluten-Free", "Dairy-Free", "Keto", "Paleo"],
			default=[]
		)

		if st.button("Generate Recipe", type="primary"):
			if not ingredients:
				st.error("Please enter at least one ingredient!")
				return

			with st.spinner("Creating your recipe... This may take a few minutes."):
				try:
					recipe_system = RecipeGenerationSystem()
					recipe_data = recipe_system.generate_recipe(
						ingredients=ingredients,
						calories=calories,
						dietary_restrictions=dietary_restrictions,
						cooking_time=cooking_time,
						skill_level=skill_level
					)
					st.session_state.recipe_data = recipe_data
					st.session_state.error = None

				except Exception as e:
					st.session_state.error = str(e)
					st.session_state.recipe_data = None

	# Main content area
	if st.session_state.get("error"):
		st.error(f"Error generating recipe: {st.session_state.error}")

	elif st.session_state.get("recipe_data"):
		try:
			recipe_data = st.session_state.recipe_data

			# Recipe section
			st.header("Generated Recipe")
			with st.expander("Recipe Details", expanded=True):
				st.markdown(recipe_data["recipe"])

			# Nutrition section
			st.header("Nutritional Information")
			with st.expander("Nutrition Details", expanded=True):
				st.markdown(recipe_data["nutrition"])

			if st.download_button(
					label="Download Recipe",
					data=json.dumps(recipe_data, indent=2),
					file_name="recipe.json",
					mime="application/json"
			):
				st.success("Recipe downloaded!")

		except Exception as e:
			st.error(f"Error displaying recipe: {str(e)}")

	# Log user count for admin (hidden from public view)
	total_users = get_user_count(conn)
	logger.info(f"Total registered users: {total_users}")


if __name__ == "__main__":
	main()
