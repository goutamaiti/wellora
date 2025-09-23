from flask import Flask, render_template, request, jsonify, url_for
from openai import OpenAI
import os
import math
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Initialize OpenRouter API - get key from environment variable
api_key = os.getenv('OPENAI_API_KEY')
if api_key:
    # OpenRouter uses OpenAI-compatible API
    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1"
    )
    print("✅ OpenRouter API configured successfully - Using DeepSeek V3.1")
    print(f"🔑 API Key Preview: {api_key[:15]}...{api_key[-10:]}")
else:
    client = None
    print("❌ Warning: OPENAI_API_KEY not found in environment variables")
    print("🔑 Add your OpenRouter API key to .env file to get AI-powered food recommendations")

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

def get_food_recommendations(region, calorie_limit, food_preference):
    """Get food recommendations from OpenRouter API only"""
    # If no API client is available, return error message
    if client is None:
        print("❌ OpenRouter API not available - No API key found")
        return """
        <div class="error-message">
            <h4>⚠️ API Configuration Required</h4>
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
        
        prompt = f"""
        Provide a complete daily meal plan from {region} state cuisine (India) that would fit within a {calorie_limit} calorie daily diet.
        IMPORTANT: The meal plan should be {preference_text}.
        Give me 3 traditional dishes: one for Breakfast, one for Lunch, and one for Dinner from {region}.
        
        For each meal recommendation, include:
        1. The name of the traditional dish from {region} (ensure it matches the {preference_text} requirement)
        2. Approximate calorie count (distribute calories appropriately across meals)
        3. Brief description with regional context
        4. Nutritional benefits of ingredients used in {region}
        
        Format the response as HTML organized by meal times:
        <div class="meal-plan">
            <div class="meal-section">
                <div class="meal-title">
                    <span class="meal-icon">🌅</span>
                    Breakfast
                </div>
                <div class="food-card">
                    <h4>Traditional Breakfast Dish Name</h4>
                    <p class="food-calories">XXX calories</p>
                    <p class="food-description">Traditional description</p>
                </div>
            </div>
            <div class="meal-section">
                <div class="meal-title">
                    <span class="meal-icon">☀️</span>
                    Lunch
                </div>
                <div class="food-card">
                    <h4>Traditional Lunch Dish Name</h4>
                    <p class="food-calories">XXX calories</p>
                    <p class="food-description">Traditional description</p>
                </div>
            </div>
            <div class="meal-section">
                <div class="meal-title">
                    <span class="meal-icon">🌙</span>
                    Dinner
                </div>
                <div class="food-card">
                    <h4>Traditional Dinner Dish Name</h4>
                    <p class="food-calories">XXX calories</p>
                    <p class="food-description">Traditional description</p>
                </div>
            </div>
        </div>
        """
        
        print(f"🔄 Making API call for {region} cuisine, {calorie_limit} calories, {preference_text}")
        
        response = client.chat.completions.create(
            model="deepseek/deepseek-chat",  # Updated to DeepSeek V3.1 (free)
            messages=[
                {"role": "system", "content": f"You are a nutrition expert specializing in traditional {region} cuisine from India. Provide authentic, healthy meal recommendations."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=800,
            extra_headers={
                "HTTP-Referer": "https://bmr-calculator.up.railway.app",
                "X-Title": "BMI Calculator App"
            }
        )
        
        print("✅ DeepSeek V3.1 API call successful!")
        api_response = response.choices[0].message.content
        print(f"API Response length: {len(api_response)} characters")
        print(f"API Response preview: {api_response[:150]}...")
        return api_response
        
    except Exception as e:
        # If API call fails, return error message
        print(f"❌ DeepSeek API Error: {e}")
        return f"""
        <div class="error-message">
            <h4>⚠️ API Error</h4>
            <p>Unable to get food recommendations at this time.</p>
            <p><strong>Error:</strong> {str(e)}</p>
            <p>Please check your API key or try again later.</p>
        </div>
        """

def parse_meal_plan(html_content):
    """Parse the HTML response to extract meal information"""
    try:
        import re
        
        # If it's an error message, return None
        if 'error-message' in html_content or 'API Configuration Required' in html_content:
            return None
        
        # Extract meal sections using regex
        meal_sections = re.findall(r'<div class="meal-section">(.*?)</div>\s*</div>', html_content, re.DOTALL)
        
        meals = {}
        meal_types = ['breakfast', 'lunch', 'dinner']
        
        for i, section in enumerate(meal_sections[:3]):  # Only take first 3 meals
            meal_type = meal_types[i] if i < len(meal_types) else f'meal_{i+1}'
            
            # Extract dish name
            dish_match = re.search(r'<h4>(.*?)</h4>', section)
            dish_name = dish_match.group(1) if dish_match else f'Traditional {meal_type.title()}'
            
            # Extract calories
            calories_match = re.search(r'(\d+)\s*calories', section, re.IGNORECASE)
            calories = int(calories_match.group(1)) if calories_match else 300
            
            # Extract description
            desc_match = re.search(r'<p class="food-description">(.*?)</p>', section, re.DOTALL)
            description = desc_match.group(1).strip() if desc_match else f'Delicious {meal_type} from your selected cuisine'
            
            meals[meal_type] = {
                'description': f"{dish_name}. {description}",
                'calories': calories
            }
        
        # If we couldn't parse properly, return None
        if not meals:
            return None
        
        return meals
        
    except Exception as e:
        print(f"Error parsing meal plan: {e}")
        # Return None if parsing fails
        return None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            # Get form data
            gender = request.form.get('gender')
            age = int(request.form.get('age'))
            weight = float(request.form.get('weight'))
            height = int(request.form.get('height'))
            activity = request.form.get('activity')
            state = request.form.get('state')
            food_preference = request.form.get('food_preference')
            
            print(f"📋 Form data: {gender}, {age}y, {weight}kg, {height}cm, {activity}, {state}, {food_preference}")
            
            # Calculate BMR and calories
            bmr = calculate_bmr(gender, weight, height, age)
            daily_calories = calculate_calorie_needs(bmr, activity)
            
            print(f"🧮 BMR: {bmr}, Daily calories: {daily_calories}")
            
            # Try AI recommendations first, fallback to simple ones
            meal_plan = None
            
            # First try AI-powered recommendations if API is available
            if client is not None:
                try:
                    print("🤖 Trying AI-powered meal recommendations...")
                    meal_plan_html = get_food_recommendations(state, int(daily_calories), food_preference)
                    meal_plan = parse_meal_plan(meal_plan_html)
                    if meal_plan:
                        print("✅ AI meal recommendations successful!")
                    else:
                        print("⚠️ AI meal parsing failed")
                except Exception as e:
                    print(f"⚠️ AI recommendations failed: {e}")
            
            # If AI failed or not available, show error message
            if not meal_plan:
                print("❌ No meal recommendations available - API failed")
            
            print(f"🍽️ Final meal plan: {list(meal_plan.keys()) if meal_plan else 'None'}")
            
            return render_template('index.html', 
                                 bmr=round(bmr),
                                 daily_calories=round(daily_calories),
                                 meal_plan=meal_plan,
                                 gender=gender,
                                 age=age,
                                 weight=weight,
                                 height=height,
                                 activity=activity,
                                 state=state,
                                 food_preference=food_preference)
        except Exception as e:
            print(f"❌ Error processing form: {e}")
            return render_template('index.html', error=str(e))
    
    return render_template('index.html')

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