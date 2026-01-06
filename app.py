from flask import Flask, render_template, request, jsonify, url_for, session, redirect, flash
from openai import OpenAI
import os
import math
import json
import hashlib
import random
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this-in-production')

# Initialize OpenRouter API - get key from environment variable
api_key = os.getenv('OPENAI_API_KEY')
if api_key:
    # OpenRouter uses OpenAI-compatible API
    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1"
    )
    print("OpenRouter API configured successfully - Using DeepSeek V3.1")
    print(f"API Key Preview: {api_key[:15]}...{api_key[-10:]}")
else:
    client = None
    print("Warning: OPENAI_API_KEY not found in environment variables")
    print("Add your OpenRouter API key to .env file to get AI-powered food recommendations")

def calculate_bmr(gender, weight, height, age):
    """Calculate BMR using Mifflin-St Jeor Equation"""
    if gender == 'male':
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    return bmr

def calculate_calorie_needs(bmr, activity_level):
    """Calculate daily calorie needs based on activity level"""
    activity_multipliers = {
        'sedentary': 1.2,
        'light': 1.375,
        'moderate': 1.55,
        'very': 1.725,
        'extra': 1.9
    }
    return bmr * activity_multipliers.get(activity_level, 1.2)

# Fallback meal database for when API is unavailable
FALLBACK_MEALS = {
    'Karnataka': {
        'breakfast': {
            'vegetarian': [
                {'name': 'Bisi Bele Bath', 'calories': 350, 'description': 'Traditional Karnataka one-pot meal made with rice, lentils, and mixed vegetables, seasoned with aromatic spices. Rich in protein and fiber, this comfort food provides sustained energy throughout the morning.'},
                {'name': 'Ragi Mudde with Sambar', 'calories': 300, 'description': 'Nutritious finger millet balls served with spicy lentil curry. This high-calcium, high-fiber breakfast is a staple in rural Karnataka and provides excellent nutritional value.'},
                {'name': 'Akki Roti with Chutney', 'calories': 280, 'description': 'Soft rice flour flatbread mixed with vegetables and served with coconut chutney. Light yet filling, perfect for a healthy start to the day.'},
            ],
            'non-vegetarian': [
                {'name': 'Chicken Saaru with Akki Roti', 'calories': 380, 'description': 'Spicy chicken curry in thin gravy served with rice flatbread. High in protein and traditional Karnataka flavors, perfect for a hearty breakfast.'},
                {'name': 'Egg Dosa', 'calories': 320, 'description': 'Crispy rice crepe topped with beaten eggs and spices. Excellent source of protein and energy to start your day.'},
            ],
            'eggetarian': [
                {'name': 'Masala Dosa with Egg Bhurji', 'calories': 350, 'description': 'Crispy rice crepe with spiced scrambled eggs. Combines traditional South Indian breakfast with protein-rich eggs.'},
                {'name': 'Egg Upma', 'calories': 300, 'description': 'Semolina porridge with scrambled eggs and vegetables. Protein-packed breakfast that keeps you full longer.'},
            ]
        },
        'lunch': {
            'vegetarian': [
                {'name': 'Sambar Rice with Gojju', 'calories': 450, 'description': 'Lentil curry mixed with steamed rice served with tangy vegetable curry. Complete meal with protein, carbs, and essential nutrients from various vegetables.'},
                {'name': 'Jolada Rotti with Ennegai', 'calories': 420, 'description': 'Sorghum flatbread with stuffed brinjal curry. High in fiber and nutrients, this traditional meal supports digestive health.'},
                {'name': 'Vangi Bath', 'calories': 400, 'description': 'Aromatic rice dish cooked with brinjal and special spice mix. Rich in antioxidants and flavorful Karnataka specialty.'},
            ],
            'non-vegetarian': [
                {'name': 'Chicken Pulao', 'calories': 520, 'description': 'Fragrant rice cooked with chicken and aromatic spices. Complete meal with high protein content and balanced nutrition.'},
                {'name': 'Mutton Saaru with Rice', 'calories': 550, 'description': 'Spicy mutton curry in thin rasam-like gravy served with rice. Rich in protein and iron, traditional Karnataka non-vegetarian meal.'},
                {'name': 'Fish Curry with Rice', 'calories': 480, 'description': 'Coastal Karnataka style fish curry with steamed rice. Excellent source of omega-3 fatty acids and lean protein.'},
            ],
            'eggetarian': [
                {'name': 'Egg Biryani', 'calories': 480, 'description': 'Fragrant rice layered with boiled eggs and aromatic spices. Protein-rich complete meal with traditional Karnataka flavors.'},
                {'name': 'Palya with Egg Curry', 'calories': 440, 'description': 'Mixed vegetable stir-fry with egg curry and rice. Balanced meal with vegetables and protein.'},
            ]
        },
        'dinner': {
            'vegetarian': [
                {'name': 'Bisibelebath with Raita', 'calories': 380, 'description': 'Spiced rice and lentil dish served with cooling yogurt salad. Easy to digest evening meal with balanced nutrition.'},
                {'name': 'Akki Roti with Huli', 'calories': 350, 'description': 'Rice flatbread with tangy tamarind curry. Light dinner option rich in probiotics and easy on digestion.'},
                {'name': 'Ragi Mudde with Soppu Saaru', 'calories': 320, 'description': 'Finger millet balls with leafy greens curry. Nutritious dinner high in calcium and iron.'},
            ],
            'non-vegetarian': [
                {'name': 'Chicken Ghee Roast with Roti', 'calories': 420, 'description': 'Spicy roasted chicken with wheat flatbread. Protein-rich dinner with authentic Karnataka spice blend.'},
                {'name': 'Mutton Chops Masala', 'calories': 450, 'description': 'Tender mutton pieces cooked in rich spicy gravy. High protein dinner with traditional flavors.'},
                {'name': 'Fish Fry with Ragi Mudde', 'calories': 400, 'description': 'Crispy fried fish served with finger millet balls. Coastal Karnataka dinner packed with protein and nutrients.'},
            ],
            'eggetarian': [
                {'name': 'Egg Pulao with Raita', 'calories': 400, 'description': 'Fragrant rice cooked with eggs and spices, served with yogurt salad. Light yet satisfying dinner.'},
                {'name': 'Egg Korma with Roti', 'calories': 380, 'description': 'Boiled eggs in creamy curry with wheat flatbread. Protein-rich dinner with mild spices.'},
            ]
        }
    },
    'Tamil Nadu': {
        'breakfast': {
            'vegetarian': [
                {'name': 'Idli with Sambar', 'calories': 280, 'description': 'Steamed rice cakes with lentil curry. Low-calorie, easily digestible breakfast rich in probiotics.'},
                {'name': 'Pongal with Vadai', 'calories': 350, 'description': 'Savory rice and lentil porridge with lentil fritters. Comfort food packed with protein and energy.'},
                {'name': 'Appam with Coconut Milk', 'calories': 300, 'description': 'Soft rice pancakes with sweetened coconut milk. Light breakfast with good carbs and healthy fats.'},
            ],
            'non-vegetarian': [
                {'name': 'Chicken Chettinad with Appam', 'calories': 400, 'description': 'Spicy chicken curry with rice pancakes. High-protein breakfast with authentic Tamil flavors.'},
                {'name': 'Egg Dosa', 'calories': 320, 'description': 'Rice crepe topped with eggs. Protein-packed start to the day.'},
            ],
            'eggetarian': [
                {'name': 'Masala Dosa with Egg Curry', 'calories': 360, 'description': 'Stuffed rice crepe with egg curry. Complete breakfast with protein and carbs.'},
                {'name': 'Pongal with Boiled Eggs', 'calories': 330, 'description': 'Savory rice porridge with eggs. Nutritious and filling breakfast.'},
            ]
        },
        'lunch': {
            'vegetarian': [
                {'name': 'Sambar Rice with Poriyal', 'calories': 450, 'description': 'Lentil curry with rice and stir-fried vegetables. Balanced meal with complete nutrition.'},
                {'name': 'Curd Rice with Pickle', 'calories': 380, 'description': 'Yogurt mixed with rice and spices. Cooling and probiotic-rich lunch.'},
                {'name': 'Tamarind Rice with Vadai', 'calories': 420, 'description': 'Tangy rice with lentil fritters. Flavorful meal rich in antioxidants.'},
            ],
            'non-vegetarian': [
                {'name': 'Chicken Biryani', 'calories': 550, 'description': 'Aromatic rice layered with spiced chicken. Complete meal high in protein.'},
                {'name': 'Fish Curry with Rice', 'calories': 480, 'description': 'Tangy fish curry with steamed rice. Rich in omega-3 and protein.'},
                {'name': 'Mutton Kuzhambu with Rice', 'calories': 520, 'description': 'Spicy mutton curry with rice. High-protein traditional Tamil meal.'},
            ],
            'eggetarian': [
                {'name': 'Egg Biryani', 'calories': 480, 'description': 'Spiced rice with boiled eggs. Protein-rich one-pot meal.'},
                {'name': 'Egg Curry with Rice', 'calories': 440, 'description': 'Eggs in spicy gravy with rice. Balanced protein and carb lunch.'},
            ]
        },
        'dinner': {
            'vegetarian': [
                {'name': 'Idli with Coconut Chutney', 'calories': 300, 'description': 'Soft steamed rice cakes with coconut chutney. Light and easily digestible dinner.'},
                {'name': 'Pongal with Sambar', 'calories': 350, 'description': 'Rice and lentil porridge with lentil curry. Comfort dinner with balanced nutrition.'},
                {'name': 'Dosa with Tomato Chutney', 'calories': 320, 'description': 'Crispy rice crepe with tangy chutney. Light evening meal.'},
            ],
            'non-vegetarian': [
                {'name': 'Chicken 65 with Roti', 'calories': 400, 'description': 'Spicy fried chicken with flatbread. Protein-rich dinner.'},
                {'name': 'Fish Fry with Rice', 'calories': 420, 'description': 'Crispy fried fish with steamed rice. Coastal Tamil dinner.'},
                {'name': 'Mutton Chukka', 'calories': 450, 'description': 'Dry mutton preparation with spices. High-protein dinner dish.'},
            ],
            'eggetarian': [
                {'name': 'Egg Kothu Parotta', 'calories': 400, 'description': 'Shredded flatbread with eggs and spices. Satisfying dinner option.'},
                {'name': 'Egg Curry with Parotta', 'calories': 380, 'description': 'Eggs in curry with layered flatbread. Protein-packed dinner.'},
            ]
        }
    },
    'Default': {  # Generic Indian meals for states not specifically covered
        'breakfast': {
            'vegetarian': [
                {'name': 'Poha with Peanuts', 'calories': 300, 'description': 'Flattened rice cooked with vegetables and peanuts. Light, nutritious breakfast popular across India.'},
                {'name': 'Upma with Chutney', 'calories': 280, 'description': 'Semolina porridge with vegetables and coconut chutney. Quick, healthy breakfast option.'},
                {'name': 'Paratha with Curd', 'calories': 350, 'description': 'Stuffed flatbread with yogurt. Filling breakfast with good carbs and probiotics.'},
            ],
            'non-vegetarian': [
                {'name': 'Egg Paratha', 'calories': 380, 'description': 'Flatbread stuffed with eggs. High-protein breakfast.'},
                {'name': 'Chicken Sandwich', 'calories': 350, 'description': 'Grilled chicken with bread. Protein-rich breakfast option.'},
            ],
            'eggetarian': [
                {'name': 'Egg Bhurji with Bread', 'calories': 320, 'description': 'Scrambled eggs with whole wheat bread. Simple, protein-packed breakfast.'},
                {'name': 'Omelette with Toast', 'calories': 300, 'description': 'Fluffy omelette with toasted bread. Classic breakfast option.'},
            ]
        },
        'lunch': {
            'vegetarian': [
                {'name': 'Dal Rice with Sabzi', 'calories': 450, 'description': 'Lentil curry with rice and vegetable curry. Complete balanced meal.'},
                {'name': 'Rajma Chawal', 'calories': 480, 'description': 'Kidney bean curry with rice. High in protein and fiber.'},
                {'name': 'Chole with Roti', 'calories': 420, 'description': 'Chickpea curry with flatbread. Protein-rich vegetarian meal.'},
            ],
            'non-vegetarian': [
                {'name': 'Chicken Curry with Rice', 'calories': 520, 'description': 'Spiced chicken curry with steamed rice. High-protein lunch.'},
                {'name': 'Mutton Curry with Roti', 'calories': 550, 'description': 'Rich mutton curry with wheat flatbread. Hearty lunch option.'},
                {'name': 'Fish Curry with Rice', 'calories': 480, 'description': 'Fish in curry with rice. Omega-3 rich lunch.'},
            ],
            'eggetarian': [
                {'name': 'Egg Curry with Rice', 'calories': 460, 'description': 'Boiled eggs in curry gravy with rice. Balanced lunch.'},
                {'name': 'Egg Biryani', 'calories': 480, 'description': 'Spiced rice with eggs. One-pot protein meal.'},
            ]
        },
        'dinner': {
            'vegetarian': [
                {'name': 'Khichdi with Kadhi', 'calories': 350, 'description': 'Rice and lentil porridge with yogurt curry. Easy to digest dinner.'},
                {'name': 'Vegetable Pulao with Raita', 'calories': 380, 'description': 'Mixed vegetable rice with yogurt. Light evening meal.'},
                {'name': 'Paneer Bhurji with Roti', 'calories': 400, 'description': 'Scrambled cottage cheese with flatbread. High-protein dinner.'},
            ],
            'non-vegetarian': [
                {'name': 'Grilled Chicken with Salad', 'calories': 380, 'description': 'Grilled chicken breast with fresh vegetables. Lean protein dinner.'},
                {'name': 'Fish Tikka with Roti', 'calories': 400, 'description': 'Grilled fish with flatbread. Healthy protein-rich dinner.'},
                {'name': 'Chicken Soup with Bread', 'calories': 350, 'description': 'Clear chicken soup with whole wheat bread. Light evening meal.'},
            ],
            'eggetarian': [
                {'name': 'Egg Fried Rice', 'calories': 380, 'description': 'Rice stir-fried with eggs and vegetables. Balanced dinner.'},
                {'name': 'Egg Curry with Roti', 'calories': 360, 'description': 'Eggs in curry with wheat flatbread. Satisfying dinner.'},
            ]
        }
    }
}

def get_fallback_meals(region, calorie_limit, food_preference):
    """Generate fallback meal recommendations when API is unavailable"""
    # Get region data or use default
    region_data = FALLBACK_MEALS.get(region, FALLBACK_MEALS['Default'])
    
    # Map mixed preference to vegetarian as fallback
    pref_key = food_preference if food_preference in ['vegetarian', 'non-vegetarian', 'eggetarian'] else 'vegetarian'
    
    # Calculate calorie distribution
    breakfast_calories = int(calorie_limit * 0.25)
    lunch_calories = int(calorie_limit * 0.40)
    dinner_calories = int(calorie_limit * 0.35)
    
    # Select meals
    meals = {}
    for meal_type, target_calories in [('breakfast', breakfast_calories), ('lunch', lunch_calories), ('dinner', dinner_calories)]:
        available_meals = region_data[meal_type].get(pref_key, region_data[meal_type]['vegetarian'])
        # Pick a random meal from the available options
        meal = random.choice(available_meals)
        
        # Adjust calories to be closer to target with some variation
        adjusted_calories = int(target_calories * random.uniform(0.9, 1.1))
        adjusted_calories = max(200, min(adjusted_calories, target_calories + 100))  # Keep within reasonable range
        
        meals[meal_type] = {
            'description': f"{meal['name']}. {meal['description']}",
            'calories': adjusted_calories
        }
    
    return meals

def get_food_recommendations(region, city, calorie_limit, food_preference, previous_meals=None):
    """Get food recommendations from OpenRouter API only"""
    # If no API client is available, return error message
    if client is None:
        print("OpenRouter API not available - No API key found")
        return """
        <div class="error-message">
            <h4>API Configuration Required</h4>
            <p>To get personalized food recommendations, please configure your OpenRouter API key in the environment variables.</p>
            <p>Visit <a href="https://openrouter.ai/keys" target="_blank">https://openrouter.ai/keys</a> to get your free API key.</p>
        </div>
        """
    
    try:
        # Create dietary preference text for prompt
        preference_text = {
            'vegetarian': 'strictly vegetarian (no meat, poultry, fish or seafood)',
            'non-vegetarian': 'non-vegetarian (can include meat, poultry, fish and seafood)',
            'eggetarian': 'eggetarian (vegetarian diet with eggs allowed)',
            'mixed': 'mixed diet (combination of vegetarian and non-vegetarian options)'
        }.get(food_preference, 'mixed diet')
        
        # Add previous meals context if provided
        previous_meals_text = ""
        if previous_meals:
            previous_meals_text = f"\nIMPORTANT: Avoid recommending these recently suggested meals: {', '.join(previous_meals[:10])}\nProvide NEW and DIFFERENT meal options to ensure variety."
        
        # Include city-specific context if available
        location_context = f"{region} state"
        if city and city != "":
            location_context = f"{city} city, {region} state"
        
        # Calculate calorie distribution for meals
        breakfast_calories = int(calorie_limit * 0.25)  # 25% for breakfast
        lunch_calories = int(calorie_limit * 0.40)      # 40% for lunch
        dinner_calories = int(calorie_limit * 0.35)     # 35% for dinner
        
        prompt = f"""You are a nutritionist expert specializing in authentic Indian regional cuisine. Create a personalized daily meal plan for {location_context} with the following strict requirements:

DIETARY REQUIREMENTS:
- Total daily calories: {calorie_limit}
- Meal distribution: Breakfast (~{breakfast_calories} cal), Lunch (~{lunch_calories} cal), Dinner (~{dinner_calories} cal)
- Diet type: {preference_text}
- Regional focus: Authentic dishes from {location_context}
{previous_meals_text}

MEAL REQUIREMENTS:
1. Each meal must be a SINGLE traditional dish (not multiple items)
2. Use only authentic recipes from {location_context}
3. Include regional cooking methods and local ingredients
4. Ensure dietary restrictions are followed strictly
5. Provide accurate calorie counts based on standard serving sizes
6. Mention key nutritional benefits and local significance

OUTPUT FORMAT (Must follow exactly):
<div class="meal-plan">
    <div class="meal-section">
        <div class="meal-title">Breakfast</div>
        <div class="food-card">
            <h4>[Authentic Breakfast Dish Name in English]</h4>
            <p class="food-calories">{breakfast_calories} calories</p>
            <p class="food-description">[2-3 sentence description including: main ingredients, preparation method, why it's popular in {location_context}, and key nutritional benefits]</p>
        </div>
    </div>
    <div class="meal-section">
        <div class="meal-title">Lunch</div>
        <div class="food-card">
            <h4>[Authentic Lunch Dish Name in English]</h4>
            <p class="food-calories">{lunch_calories} calories</p>
            <p class="food-description">[2-3 sentence description including: main ingredients, preparation method, why it's popular in {location_context}, and key nutritional benefits]</p>
        </div>
    </div>
    <div class="meal-section">
        <div class="meal-title">Dinner</div>
        <div class="food-card">
            <h4>[Authentic Dinner Dish Name in English]</h4>
            <p class="food-calories">{dinner_calories} calories</p>
            <p class="food-description">[2-3 sentence description including: main ingredients, preparation method, why it's popular in {location_context}, and key nutritional benefits]</p>
        </div>
    </div>
</div>

IMPORTANT: Only respond with the HTML structure above. Do not add any extra text, explanations, or formatting outside the specified structure."""

        
        print(f"Making API call for {region} cuisine, {calorie_limit} calories, {preference_text}")
        
        response = client.chat.completions.create(
            model="deepseek/deepseek-chat",  # Updated to DeepSeek V3.1 (free)
            messages=[
                {"role": "system", "content": f"You are a certified nutritionist and culinary expert with deep knowledge of traditional Indian regional cuisines. Your expertise covers authentic recipes, nutritional values, and cultural significance of dishes from all Indian states. You provide precise, culturally accurate meal recommendations with exact calorie calculations based on standard serving sizes. Always follow the user's dietary restrictions strictly and focus on authentic local dishes from the specified region."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.7,  # Add some creativity while maintaining accuracy
            extra_headers={
                "HTTP-Referer": "https://bmr-calculator.up.railway.app",
                "X-Title": "BMI Calculator App"
            }
        )
        
        print("DeepSeek V3.1 API call successful!")
        api_response = response.choices[0].message.content
        print(f"API Response length: {len(api_response)} characters")
        print(f"API Response preview: {api_response[:150]}...")
        return api_response
        
    except Exception as e:
        # If API call fails, use fallback recommendations
        print(f"DeepSeek API Error: {e}")
        print(f"Using fallback meal recommendations for {region}")
        
        # Return None to trigger fallback in caller
        return None

def parse_meal_plan(html_content):
    """Parse the HTML response to extract meal information with improved error handling"""
    try:
        # If it's an error message, return None
        if 'error-message' in html_content or 'API Configuration Required' in html_content:
            return None
        
        print(f"Parsing HTML content (length: {len(html_content)})")
        
        # Extract meal sections using more flexible regex patterns
        meal_sections = re.findall(r'<div class="meal-section">(.*?)</div>\s*</div>', html_content, re.DOTALL)
        
        # If the first pattern doesn't work, try alternative patterns
        if not meal_sections:
            meal_sections = re.findall(r'<div class="meal-section">(.*?)</div>', html_content, re.DOTALL | re.MULTILINE)
        
        meals = {}
        meal_types = ['breakfast', 'lunch', 'dinner']
        
        print(f"Found {len(meal_sections)} meal sections")
        
        for i, section in enumerate(meal_sections[:3]):  # Only take first 3 meals
            meal_type = meal_types[i] if i < len(meal_types) else f'meal_{i+1}'
            
            print(f"Processing {meal_type} section: {section[:100]}...")
            
            # Extract dish name with multiple patterns
            dish_match = re.search(r'<h4[^>]*>(.*?)</h4>', section, re.DOTALL)
            if not dish_match:
                dish_match = re.search(r'<h3[^>]*>(.*?)</h3>', section, re.DOTALL)
            
            dish_name = dish_match.group(1).strip() if dish_match else f'Traditional {meal_type.title()}'
            dish_name = re.sub(r'<.*?>', '', dish_name)  # Remove any HTML tags from dish name
            
            # Extract calories with more flexible patterns
            calories_match = re.search(r'(\d+)\s*(?:calories?|cal|kcal)', section, re.IGNORECASE)
            if not calories_match:
                # Look for numbers that might be calories (typically 100-800 range for individual meals)
                number_matches = re.findall(r'\b(\d{2,3})\b', section)
                potential_calories = [int(n) for n in number_matches if 100 <= int(n) <= 800]
                calories = potential_calories[0] if potential_calories else 300
            else:
                calories = int(calories_match.group(1))
            
            # Extract description with flexible patterns
            desc_match = re.search(r'<p class="food-description"[^>]*>(.*?)</p>', section, re.DOTALL)
            if not desc_match:
                desc_match = re.search(r'<p[^>]*>(.*?)</p>', section, re.DOTALL)
            
            if desc_match:
                description = desc_match.group(1).strip()
                description = re.sub(r'<.*?>', '', description)  # Remove HTML tags
                description = re.sub(r'\s+', ' ', description)   # Normalize whitespace
            else:
                description = f'Authentic {meal_type} dish with traditional ingredients and regional flavors'
            
            meals[meal_type] = {
                'description': f"{dish_name}. {description}",
                'calories': calories
            }
            
            print(f"Parsed {meal_type}: {dish_name} ({calories} cal)")
        
        # If we couldn't parse properly, return None
        if not meals:
            print("No meals parsed successfully")
            return None
        
        print(f"Successfully parsed {len(meals)} meals")
        return meals
        
    except Exception as e:
        print(f"Error parsing meal plan: {e}")
        # Return None if parsing fails
        return None

# User Data Management Functions
def load_user_data():
    """Load user data from JSON file"""
    try:
        with open('user_data.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"users": {}}
    except json.JSONDecodeError:
        return {"users": {}}

def save_user_data(data):
    """Save user data to JSON file"""
    try:
        with open('user_data.json', 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving user data: {e}")
        return False

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    """Verify password against hash"""
    return hash_password(password) == hashed

def create_user(username, email, password):
    """Create a new user account"""
    data = load_user_data()
    
    # Check if user already exists
    if username in data['users']:
        return False, "Username already exists"
    
    # Check if email already exists
    for user_data in data['users'].values():
        if user_data.get('email') == email:
            return False, "Email already registered"
    
    # Create new user
    data['users'][username] = {
        'username': username,
        'email': email,
        'password_hash': hash_password(password),
        'created_at': datetime.now().isoformat(),
        'profile': {},
        'bmr_history': [],
        'meal_history': [],
        'goals': {
            'daily_water': {'target': 8, 'completed': False, 'date_completed': None},
            'daily_exercise': {'target': '30 minutes', 'completed': False, 'date_completed': None},
            'healthy_meals': {'target': 3, 'completed': False, 'date_completed': None},
            'sleep_hours': {'target': 8, 'completed': False, 'date_completed': None},
            'meditation': {'target': '10 minutes', 'completed': False, 'date_completed': None}
        },
        'progress': {
            'total_goals': 5,
            'completed_today': 0,
            'completion_percentage': 0,
            'streak_days': 0,
            'last_activity': datetime.now().date().isoformat()
        },
        'settings': {
            'email_notifications': True,
            'preferred_meal_types': [],
            'dietary_restrictions': [],
            'favorite_cuisines': []
        }
    }
    
    if save_user_data(data):
        return True, "User created successfully"
    else:
        return False, "Error saving user data"

def authenticate_user(username, password):
    """Authenticate user login"""
    data = load_user_data()
    
    if username not in data['users']:
        return False, "User not found"
    
    user_data = data['users'][username]
    if verify_password(password, user_data['password_hash']):
        return True, "Login successful"
    else:
        return False, "Invalid password"

def get_user_data(username):
    """Get user data by username"""
    data = load_user_data()
    if username in data['users']:
        return data['users'][username]
    return None

def update_user_progress(username, goal_id):
    """Update user progress for a specific goal"""
    data = load_user_data()
    
    if username not in data['users']:
        return False
    
    user = data['users'][username]
    today = datetime.now().date().isoformat()
    
    if goal_id in user['goals']:
        user['goals'][goal_id]['completed'] = True
        user['goals'][goal_id]['date_completed'] = today
        
        # Update progress
        completed_count = sum(1 for goal in user['goals'].values() if goal['completed'])
        user['progress']['completed_today'] = completed_count
        user['progress']['completion_percentage'] = (completed_count / user['progress']['total_goals']) * 100
        user['progress']['last_activity'] = today
        
        # Update streak if all goals completed
        if completed_count == user['progress']['total_goals']:
            user['progress']['streak_days'] += 1
        
        return save_user_data(data)
    
    return False

def add_meal_to_history(username, meal_plan):
    """Add meal plan to user's history"""
    data = load_user_data()
    
    if username not in data['users']:
        return False
    
    user = data['users'][username]
    today = datetime.now().date().isoformat()
    
    # Create meal plan array
    meal_descriptions = []
    if meal_plan:
        for meal_type, meal_info in meal_plan.items():
            meal_descriptions.append(f"{meal_type.title()}: {meal_info['description']}")
    
    # Add to history
    meal_entry = {
        'date': today,
        'meal_plan': meal_descriptions
    }
    
    user['meal_history'].append(meal_entry)
    
    # Keep only last 30 days of history
    if len(user['meal_history']) > 30:
        user['meal_history'] = user['meal_history'][-30:]
    
    return save_user_data(data)

def get_previous_meals(username, days=7):
    """Get user's previous meal recommendations to avoid duplicates"""
    data = load_user_data()
    
    if username not in data['users']:
        return []
    
    user = data['users'][username]
    recent_meals = []
    
    # Get meals from last X days
    cutoff_date = datetime.now().date() - timedelta(days=days)
    
    for meal_entry in user['meal_history']:
        entry_date = datetime.fromisoformat(meal_entry['date']).date()
        if entry_date >= cutoff_date:
            recent_meals.extend(meal_entry['meal_plan'])
    
    return recent_meals

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login and signup page"""
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        username = request.form.get('username')
        password = request.form.get('password')
        
        if form_type == 'login':
            # Handle login
            success, message = authenticate_user(username, password)
            if success:
                session['username'] = username
                session['logged_in'] = True
                flash('Login successful!', 'success')
                return redirect(url_for('calculator'))
            else:
                flash(message, 'error')
        
        elif form_type == 'signup':
            # Handle signup
            email = request.form.get('email')
            confirm_password = request.form.get('confirm_password')
            
            if password != confirm_password:
                flash('Passwords do not match', 'error')
            else:
                success, message = create_user(username, email, password)
                if success:
                    flash(message, 'success')
                    # Auto-login after successful signup
                    session['username'] = username
                    session['logged_in'] = True
                    return redirect(url_for('calculator'))
                else:
                    flash(message, 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout route"""
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('landing'))

@app.route('/progress/update', methods=['POST'])
def update_progress():
    """Update user progress"""
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})
    
    goal_id = request.form.get('goal_id')
    completed = request.form.get('completed') == 'true'
    
    if completed:
        success = update_user_progress(session['username'], goal_id)
        return jsonify({'success': success})
    else:
        # Handle unchecking goals if needed
        return jsonify({'success': True})

@app.route('/')
def index():
    """Landing page route"""
    return render_template('landing.html')

# Alternative route for landing
@app.route('/landing')
def landing():
    """Alternative landing page route"""
    return render_template('landing.html')

@app.route('/calculator', methods=['GET', 'POST'])
def calculator():
    """BMR Calculator page route - requires login"""
    if 'username' not in session:
        flash('Please login to access the calculator', 'error')
        return redirect(url_for('login'))
    
    username = session['username']
    user_data = get_user_data(username)
    
    if request.method == 'POST':
        try:
            # Get form data
            gender = request.form.get('gender')
            age = int(request.form.get('age'))
            weight = float(request.form.get('weight'))
            height = int(request.form.get('height'))
            activity = request.form.get('activity')
            state = request.form.get('state')
            city = request.form.get('city')
            food_preference = request.form.get('food_preference')
            
            print(f"Form data: {gender}, {age}y, {weight}kg, {height}cm, {activity}, {state}, {city}, {food_preference}")
            
            # Calculate BMR and calories
            bmr = calculate_bmr(gender, weight, height, age)
            daily_calories = calculate_calorie_needs(bmr, activity)
            
            print(f"BMR: {bmr}, Daily calories: {daily_calories}")
            
            # Update user profile with latest data
            data = load_user_data()
            if username in data['users']:
                data['users'][username]['profile'] = {
                    'age': age,
                    'gender': gender,
                    'height': height,
                    'weight': weight,
                    'activity_level': activity,
                    'food_preference': food_preference,
                    'state': state,
                    'city': city
                }
                # Add BMR to history
                today = datetime.now().date().isoformat()
                bmr_entry = {
                    'date': today,
                    'bmr': round(bmr),
                    'tdee': round(daily_calories),
                    'goal_calories': round(daily_calories)
                }
                data['users'][username]['bmr_history'].append(bmr_entry)
                
                # Keep only last 30 entries
                if len(data['users'][username]['bmr_history']) > 30:
                    data['users'][username]['bmr_history'] = data['users'][username]['bmr_history'][-30:]
                
                save_user_data(data)
            
            # Get previous meals to avoid duplicates
            previous_meals = get_previous_meals(username, days=7)
            
            # Try AI recommendations first, fallback to simple ones
            meal_plan = None
            
            # First try AI-powered recommendations if API is available
            if client is not None:
                try:
                    print("Trying AI-powered meal recommendations...")
                    # Include previous meals in prompt to avoid duplicates
                    meal_plan_html = get_food_recommendations(state, city, int(daily_calories), food_preference, previous_meals)
                    if meal_plan_html:  # Check if we got a response
                        meal_plan = parse_meal_plan(meal_plan_html)
                        if meal_plan:
                            print("AI meal recommendations successful!")
                            # Add to user's meal history
                            add_meal_to_history(username, meal_plan)
                        else:
                            print("AI meal parsing failed, using fallback")
                    else:
                        print("API returned None, using fallback")
                except Exception as e:
                    print(f"AI recommendations failed: {e}, using fallback")
            
            # If AI failed or not available, use fallback meals
            if not meal_plan:
                print(f"Using fallback meal recommendations for {state}")
                meal_plan = get_fallback_meals(state, int(daily_calories), food_preference)
                if meal_plan:
                    print("Fallback meal recommendations successful!")
                    # Add to user's meal history
                    add_meal_to_history(username, meal_plan)
            
            print(f"Final meal plan: {list(meal_plan.keys()) if meal_plan else 'None'}")
            
            return render_template('calculator.html', 
                                 bmr=round(bmr),
                                 daily_calories=round(daily_calories),
                                 meal_plan=meal_plan,
                                 user_data=user_data,
                                 previous_meals=previous_meals[:5],  # Show last 5 meals
                                 gender=gender,
                                 age=age,
                                 weight=weight,
                                 height=height,
                                 activity=activity,
                                 state=state,
                                 city=city,
                                 food_preference=food_preference)
        except Exception as e:
            print(f"Error processing form: {e}")
            return render_template('calculator.html', error=str(e), user_data=user_data)
    
    # GET request - pre-populate form with user data if available
    template_data = {'user_data': user_data}
    if user_data and 'profile' in user_data:
        profile = user_data['profile']
        template_data.update({
            'gender': profile.get('gender', ''),
            'age': profile.get('age', ''),
            'weight': profile.get('weight', ''),
            'height': profile.get('height', ''),
            'activity': profile.get('activity_level', ''),
            'state': profile.get('state', ''),
            'city': profile.get('city', ''),
            'food_preference': profile.get('food_preference', '')
        })
    
    return render_template('calculator.html', **template_data)

@app.route('/about')
def about():
    """About page route"""
    return render_template('about.html')

@app.route('/breathe')
def breathe():
    """Breathing exercise page route"""
    return render_template('breathe.html')

@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        # Get form data
        gender = request.form.get('gender')
        weight = float(request.form.get('weight'))
        height = float(request.form.get('height'))
        age = int(request.form.get('age'))
        activity = request.form.get('activity')
        state = request.form.get('state')  # Changed from 'region' to 'state' to match HTML form
        food_preference = request.form.get('food_preference')
        
        # Validate inputs
        if not all([gender, weight, height, age, activity, state, food_preference]):
            return jsonify({
                'success': False,
                'error': 'All fields are required'
            })
        
        if weight <= 0 or height <= 0 or age <= 0:
            return jsonify({
                'success': False,
                'error': 'Weight, height, and age must be positive values'
            })
        
        # Calculate BMR and calorie needs
        bmr = calculate_bmr(gender, weight, height, age)
        calorie_needs = calculate_calorie_needs(bmr, activity)
        
        # Get food recommendations - try API first, then fallback
        recommendations_html = None
        recommendations = None
        
        if client is not None:
            try:
                recommendations_html = get_food_recommendations(state, '', int(calorie_needs), food_preference)
                if recommendations_html:
                    recommendations = parse_meal_plan(recommendations_html)
            except Exception as e:
                print(f"API recommendations failed in /calculate: {e}")
        
        # Use fallback if API failed
        if not recommendations:
            recommendations = get_fallback_meals(state, int(calorie_needs), food_preference)
        
        # Return results as JSON
        return jsonify({
            'success': True,
            'bmr': round(bmr),
            'calorie_needs': round(calorie_needs),
            'recommendations': recommendations
        })
    except Exception as e:
        print(f"Error in calculate route: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Add a test route to debug
@app.route('/test', methods=['GET', 'POST'])
def test():
    if request.method == 'GET':
        return jsonify({'message': 'GET request works', 'methods': ['GET', 'POST']})
    else:
        return jsonify({'message': 'POST request works', 'data': dict(request.form)})

@app.route('/test-api')
def test_api():
    """Test API connection directly"""
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return jsonify({'error': 'No API key found', 'status': 'failed'})
        
        client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )
        
        response = client.chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=[
                {"role": "user", "content": "Generate one simple Karnataka breakfast dish with calories. Format: Dish Name - 300 calories - Description"}
            ],
            max_tokens=100
        )
        
        return jsonify({
            'status': 'success',
            'api_response': response.choices[0].message.content,
            'model': 'deepseek/deepseek-chat'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        })

@app.route('/meal/completion', methods=['POST', 'GET'])
def meal_completion():
    """Save or retrieve meal completion status for tracking nutrition progress"""
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    username = session['username']
    
    if request.method == 'GET':
        # Retrieve meal completions
        date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        try:
            user_data_dict = load_user_data()
            
            completed_meals = []
            if ('users' in user_data_dict and 
                username in user_data_dict['users'] and 
                'meal_completions' in user_data_dict['users'][username] and
                date in user_data_dict['users'][username]['meal_completions']):
                
                completed_meals = user_data_dict['users'][username]['meal_completions'][date]
            
            return jsonify({'success': True, 'completed_meals': completed_meals})
        
        except Exception as e:
            print(f"Error retrieving meal completion: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    else:  # POST method
        # Save meal completions
        try:
            data = request.get_json()
            completed_meals = data.get('completed_meals', [])
            date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
            
            user_data_dict = load_user_data()
            
            if 'users' not in user_data_dict:
                user_data_dict['users'] = {}
            
            if username not in user_data_dict['users']:
                user_data_dict['users'][username] = {}
            
            if 'meal_completions' not in user_data_dict['users'][username]:
                user_data_dict['users'][username]['meal_completions'] = {}
            
            user_data_dict['users'][username]['meal_completions'][date] = completed_meals
            
            save_user_data(user_data_dict)
            
            return jsonify({'success': True})
        
        except Exception as e:
            print(f"Error saving meal completion: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

# Add error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Route not found'}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Method not allowed for this route'}), 405

if __name__ == '__main__':
    # Use environment port for deployment, fallback to 5000 for local
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)