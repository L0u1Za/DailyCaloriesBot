from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from dotenv import load_dotenv
import os
import asyncio
import requests

load_dotenv()

# Tokens from .env file
BOT_TOKEN = os.getenv('BOT_TOKEN')
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# In-memory user data storage
users = {}

class UserProfile(StatesGroup):
    weight = State()
    height = State()
    age = State()
    activity = State()
    city = State()

def calculate_water_goal(weight, activity, temperature):
    base_water = weight * 30  # ml/kg
    activity_water = (activity // 30) * 500  # ml for every 30 mins
    weather_water = 500 if temperature > 25 else 0
    return base_water + activity_water + weather_water

def calculate_calorie_goal(weight, height, age, activity):
    base_calories = 10 * weight + 6.25 * height - 5 * age
    activity_calories = (activity // 30) * 100  # approx. extra calories per 30 mins activity
    return base_calories + activity_calories

# Function to fetch current weather data from OpenWeatherMap API
async def get_temperature(city):
    params = {
        "q": city,
        "appid": WEATHER_API_KEY,
        "units": "metric",
    }
    response = requests.get('http://api.openweathermap.org/data/2.5/weather', params=params).json()
    if response.get("cod") == 401:
        raise ValueError("Invalid API key. Please see https://openweathermap.org/faq#error401 for more info.")
    else:
        current_temp = response['main']['temp']
    return current_temp

@dp.message(Command("start"))
async def send_welcome(message: Message):
    await message.answer(
        """Hi! I'm your fitness tracker bot. Use /set_profile to set up your profile.
Commands:
/set_profile - Set your profile
/log_water - Log water consumption
/log_food - Log food consumption
/log_workout - Log a workout
/check_progress - Check your progress"""
    )

@dp.message(Command("set_profile"))
async def set_profile(message: Message, state: FSMContext):
    await message.answer("Enter your weight (in kg):")
    await state.set_state(UserProfile.weight)

@dp.message(UserProfile.weight)
async def process_weight(message: Message, state: FSMContext):
    try:
        weight = int(message.text)
        await state.update_data(weight=weight)
        await message.answer("Enter your height (in cm):")
        await state.set_state(UserProfile.height)
    except ValueError:
        await message.answer("Please enter a valid number.")

@dp.message(UserProfile.height)
async def process_height(message: Message, state: FSMContext):
    try:
        height = int(message.text)
        await state.update_data(height=height)
        await message.answer("Enter your age:")
        await state.set_state(UserProfile.age)
    except ValueError:
        await message.answer("Please enter a valid number.")

@dp.message(UserProfile.age)
async def process_age(message: Message, state: FSMContext):
    try:
        age = int(message.text)
        await state.update_data(age=age)
        await message.answer("How many minutes of activity do you do daily?")
        await state.set_state(UserProfile.activity)
    except ValueError:
        await message.answer("Please enter a valid number.")

@dp.message(UserProfile.activity)
async def process_activity(message: Message, state: FSMContext):
    try:
        activity = int(message.text)
        await state.update_data(activity=activity)
        await message.answer("Which city are you in? (for weather data):")
        await state.set_state(UserProfile.city)
    except ValueError:
        await message.answer("Please enter a valid number.")

@dp.message(UserProfile.city)
async def process_city(message: Message, state: FSMContext):
    try:
        city = message.text
        temperature = await get_temperature(city)
        user_data = await state.get_data()
        weight = user_data['weight']
        height = user_data['height']
        age = user_data['age']
        activity = user_data['activity']

        water_goal = calculate_water_goal(weight, activity, temperature)
        calorie_goal = calculate_calorie_goal(weight, height, age, activity)

        user_id = message.from_user.id
        users[user_id] = {
            'weight': weight,
            'height': height,
            'age': age,
            'activity': activity,
            'city': city,
            'water_goal': water_goal,
            'calorie_goal': calorie_goal,
            'logged_water': 0,
            'logged_calories': 0,
            'burned_calories': 0
        }

        await message.answer("Profile set up successfully! Use /check_progress to see your goals.")
        await state.clear()
    except ValueError:
        await message.answer("Please enter a valid city.")

@dp.message(Command("check_progress"))
async def check_progress(message: Message):
    user_id = message.from_user.id
    if user_id not in users:
        await message.answer("You need to set up your profile first using /set_profile.")
        return

    user_data = users.get(user_id)

    water_logged = user_data.get('logged_water', 0)
    calorie_logged = user_data.get('logged_calories', 0)
    calorie_burned = user_data.get('burned_calories', 0)

    progress = f"""
📊 Progress:
Water:
- Consumed: {water_logged} ml out of {user_data['water_goal']} ml
- Remaining: {user_data['water_goal'] - water_logged} ml

Calories:
- Consumed: {calorie_logged} kcal out of {user_data['calorie_goal']} kcal
- Burned: {calorie_burned} kcal
- Net: {calorie_logged - calorie_burned} kcal
"""
    await message.answer(progress)

@dp.message(Command("log_water"))
async def log_water(message: Message):
    try:
        user_id = message.from_user.id
        if user_id not in users:
            await message.answer("Please set up your profile first using /set_profile.")
            return

        amount = int(message.text.split()[1])
        users[user_id]['logged_water'] += amount
        remaining_water = users[user_id]['water_goal'] - users[user_id]['logged_water']

        await message.answer(
            f"Logged {amount} ml of water. Remaining: {max(0, remaining_water)} ml."
        )
    except (IndexError, ValueError):
        await message.answer("Usage: /log_water <amount_in_ml>")

@dp.message(Command("log_food"))
async def log_food(message: Message):
    try:
        user_id = message.from_user.id
        if user_id not in users:
            await message.answer("Please set up your profile first using /set_profile.")
            return

        product_name = " ".join(message.text.split()[1:]).lower()
        # Mock API response (replace with actual API call if needed)
        food_data = {
            "banana": 89,
            "apple": 52,
            "bread": 265
        }

        if product_name not in food_data:
            await message.answer("Product not found in database.")
            return

        calories_per_100g = food_data[product_name]
        await message.answer(f"{product_name.capitalize()} — {calories_per_100g} kcal per 100 g. How many grams?")

        @dp.message()
        async def process_food_amount(message: Message):
            try:
                amount = int(message.text)
                calories = (calories_per_100g / 100) * amount
                users[user_id]['logged_calories'] += calories

                await message.answer(
                    f"Logged {calories:.2f} kcal from {amount} g of {product_name}."
                )
            except ValueError:
                await message.answer("Please enter a valid amount in grams.")
    except IndexError:
        await message.answer("Usage: /log_food <product_name>")

@dp.message(Command("log_workout"))
async def log_workout(message: Message):
    try:
        user_id = message.from_user.id
        if user_id not in users:
            await message.answer("Please set up your profile first using /set_profile.")
            return

        workout_type = message.text.split()[1]
        duration = int(message.text.split()[2])

        # Mock workout data (replace with actual calculations or API calls)
        workout_data = {
            "run": 10,
            "walk": 5,
            "cycle": 8
        }

        if workout_type.lower() not in workout_data:
            await message.answer("Workout type not found. Use run, walk, or cycle.")
            return

        calories_burned_per_min = workout_data[workout_type.lower()]
        calories_burned = calories_burned_per_min * duration
        users[user_id]['burned_calories'] += calories_burned

        water_needed = (duration // 30) * 200  # Additional water needed
        users[user_id]['logged_water'] += water_needed

        await message.answer(
            f"Logged {calories_burned} kcal burned from {duration} minutes of {workout_type}. "
            f"Remember to drink an additional {water_needed} ml of water!"
        )
    except (IndexError, ValueError):
        await message.answer("Usage: /log_workout <workout_type> <duration_in_minutes>")

# Run Application
async def main():
    print("Bot started.")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
