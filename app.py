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
        'active': 1.725,
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
            <p>To get personalized food recommendations, please configure your OpenRouter API key in the .env file.</p>
            <p>Visit <a href="https://openrouter.ai/keys" target="_blank">https://openrouter.ai/keys</a> to get your free API key.</p>
        </div>
        """
    
    try:
        # Create dietary preference text for prompt
        preference_text = {
            'vegetarian': 'strictly vegetarian (no meat, poultry, fish or seafood)',
            'non_vegetarian': 'non-vegetarian (can include meat, poultry, fish and seafood)',
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
                <h4 class="meal-title">Breakfast</h4>
                <div class="food-card">
                    <h5>Traditional Breakfast Dish Name</h5>
                    <p class="food-calories">XXX calories</p>
                    <p class="food-description">Traditional description</p>
                </div>
            </div>
            <div class="meal-section">
                <h4 class="meal-title">Lunch</h4>
                <div class="food-card">
                    <h5>Traditional Lunch Dish Name</h5>
                    <p class="food-calories">XXX calories</p>
                    <p class="food-description">Traditional description</p>
                </div>
            </div>
            <div class="meal-section">
                <h4 class="meal-title">Dinner</h4>
                <div class="food-card">
                    <h5>Traditional Dinner Dish Name</h5>
                    <p class="food-calories">XXX calories</p>
                    <p class="food-description">Traditional description</p>
                </div>
            </div>
        </div>
        """
        
        response = client.chat.completions.create(
            model="deepseek/deepseek-chat",  # Updated to DeepSeek V3.1 (free)
            messages=[
                {"role": "system", "content": "You are a nutrition expert providing healthy food recommendations."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            extra_headers={
                "HTTP-Referer": "http://localhost:5000",
                "X-Title": "BMI Calculator App"
            }
        )
        
        print("✅ DeepSeek V3.1 API call successful!")
        return response.choices[0].message.content
        
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

@app.route('/')
def index():
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
        region = request.form.get('region')
        food_preference = request.form.get('food_preference')
        
        # Validate inputs
        if not all([gender, weight, height, age, activity, region, food_preference]):
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
        recommendations = get_food_recommendations(region, calorie_needs, food_preference)
        
        # Return results as JSON
        return jsonify({
            'success': True,
            'bmr': round(bmr),
            'calorie_needs': round(calorie_needs),
            'recommendations': recommendations
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    app.run(debug=True)