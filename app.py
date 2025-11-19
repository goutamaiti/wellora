from flask import Flask, render_template, request, jsonify, url_for, session, redirect, flash
from openai import OpenAI
import os
import math
import json
import hashlib
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
        # If API call fails, return error message
        print(f"DeepSeek API Error: {e}")
        return f"""
        <div class="error-message">
            <h4>API Error</h4>
            <p>Unable to get food recommendations at this time.</p>
            <p><strong>Error:</strong> {str(e)}</p>
            <p>Please check your API key or try again later.</p>
        </div>
        """

def parse_meal_plan(html_content):
    """Parse the HTML response to extract meal information with improved error handling"""
    try:
        import re
        
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
                    meal_plan = parse_meal_plan(meal_plan_html)
                    if meal_plan:
                        print("AI meal recommendations successful!")
                        # Add to user's meal history
                        add_meal_to_history(username, meal_plan)
                    else:
                        print("AI meal parsing failed")
                except Exception as e:
                    print(f"AI recommendations failed: {e}")
            
            # If AI failed or not available, show error message
            if not meal_plan:
                print("No meal recommendations available - API failed")
            
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
        
        # Get food recommendations
        recommendations = get_food_recommendations(state, calorie_needs, food_preference)
        
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