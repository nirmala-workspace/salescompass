import os
import json
from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv('SECRET_KEY', 'salescompass2024')
CORS(app)

# Initialize Groq client
client = Groq(api_key=os.getenv('GROQ_API_KEY'))

# Load product data
def load_products():
    with open('data/products.json', 'r') as f:
        return json.load(f)

def build_product_context(user_type='sales'):
    products = load_products()
    context = f"You are SalesCompass AI, a product knowledge assistant for {products['company']}.\n\n"
    context += "PRODUCT CATALOGUE:\n\n"
    
    for category in products['categories']:
        context += f"=== {category['name']} ===\n"
        for p in category['products']:
            context += f"SKU: {p['sku']} | {p['name']}\n"
            context += f"Specs: {p['specs']}\n"
            if user_type == 'distribution':
                context += f"Price: Rs. {p['distribution_price']} (Distribution) | Rs. {p['retail_price']} (Retail)\n"
            else:
                context += f"Price: Rs. {p['retail_price']}\n"
            context += f"Stock: {p['stock']}\n\n"
    
    return context

# Store conversation history per session
conversations = {}

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    password = data.get('password', '')
    
    if password == os.getenv('DISTRIBUTION_PASSWORD', 'dist@123'):
        session['user_type'] = 'distribution'
        session['logged_in'] = True
        return jsonify({'success': True, 'user_type': 'distribution', 'message': 'Welcome! Distribution pricing enabled.'})
    elif password == os.getenv('SALES_PASSWORD', 'sales@123'):
        session['user_type'] = 'sales'
        session['logged_in'] = True
        return jsonify({'success': True, 'user_type': 'sales', 'message': 'Welcome! Sales team access granted.'})
    else:
        return jsonify({'success': False, 'message': 'Invalid password. Please try again.'})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/chat', methods=['POST'])
def chat():
    if not session.get('logged_in'):
        return jsonify({'error': 'Please login first.'}), 401
    
    data = request.json
    user_message = data.get('message', '')
    session_id = session.get('user_type', 'default')
    
    # Initialize conversation history
    if session_id not in conversations:
        conversations[session_id] = []
    
    # Add user message to history
    conversations[session_id].append({
        'role': 'user',
        'content': user_message
    })
    
    # Keep last 10 messages for context
    recent_history = conversations[session_id][-10:]
    
    # Build system prompt with product context
    user_type = session.get('user_type', 'sales')
    product_context = build_product_context(user_type)
    
    system_prompt = f"""{product_context}

INSTRUCTIONS:
- You are a helpful sales assistant with full product knowledge
- Answer questions about products, specs, pricing, availability
- For comparison questions, compare products clearly
- For stock queries, mention current stock status
- Keep answers concise and useful for sales reps during client calls
- If asked about pricing, only show pricing appropriate for the user's access level
- User type: {user_type} ({"can see both distribution and retail prices" if user_type == "distribution" else "can see retail prices only"})
- Remember the full conversation context for follow-up questions
- Always mention the SKU number when discussing specific products
"""
    
    # Call Groq API with conversation history
    messages = [{'role': 'system', 'content': system_prompt}] + recent_history
    
    response = client.chat.completions.create(
        model='llama-3.3-70b-versatile',
        messages=messages,
        max_tokens=500,
        temperature=0.3
    )
    
    assistant_message = response.choices[0].message.content
    
    # Add assistant response to history
    conversations[session_id].append({
        'role': 'assistant',
        'content': assistant_message
    })
    
    return jsonify({
        'response': assistant_message,
        'user_type': user_type
    })

@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({
        'logged_in': session.get('logged_in', False),
        'user_type': session.get('user_type', None)
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)