from datetime import datetime
import os
from dotenv import load_dotenv
from typing import cast
import chainlit as cl
from agents import Agent, Runner, AsyncOpenAI, OpenAIChatCompletionsModel
from agents.run import RunConfig
import gspread

# Authenticate with Google Sheets
gc = gspread.service_account(filename="credentials.json")
sh = gc.open("MyExpenses")
worksheet = sh.sheet1

def log_expense(category, amount):
    date_str = datetime.now().strftime("%Y-%m-%d")
    worksheet.append_row([date_str, category, str(amount)])
    return f"✅ Added: {category} - {amount}"

def remove_expense(row_number):
    worksheet.delete_rows(row_number)
    return f"❌ Removed row {row_number}"

def show_expenses():
    records = worksheet.get_all_values()
    if not records:
        return "📄 No records found."
    rows = [f"{idx+1}: " + " | ".join(row) for idx, row in enumerate(records)]
    return "\n".join(rows)

def edit_expense(row_number, category, amount):
    date_str = datetime.now().strftime("%Y-%m-%d")
    worksheet.update(f"A{row_number}:C{row_number}", [[date_str, category, str(amount)]])
    return f"✏️ Edited row {row_number}: {category} - {amount}"

# Load environment variables
load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")
if not gemini_api_key:
    raise ValueError("GEMINI_API_KEY is not set.")

@cl.on_chat_start
async def start():
    external_client = AsyncOpenAI(
        api_key=gemini_api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    model = OpenAIChatCompletionsModel(
        model="gemini-2.0-flash",
        openai_client=external_client
    )
    config = RunConfig(
        model=model,
        model_provider=external_client,
        tracing_disabled=True
    )
    cl.user_session.set("chat_history", [])
    cl.user_session.set("config", config)
    agent = Agent(
        name="SimpleBot",
        instructions="You are a helpful assistant.",
        model=model
    )
    cl.user_session.set("agent", agent)

    await cl.Message(content=(
        "✨✨ ✨ ✨ ✨ ✨ ✨ ✨ **Welcome to Nousheen's ChatBot!** ✨ ✨ ✨ ✨ ✨ ✨ ✨\n"
        "*It is a chatbot that can help you add, edit, and remove expenses from your Google Sheet. It will also help you with your queries.*\n"
        "- ➕ `Add [category] [amount]`\n"
        "- ✏️ `Edit [row_number] [category] [amount]`\n"
        "- ❌ `Remove [row_number]`\n"
        "- 📄 `Show`\n"
        "- 💬 Or ask anything."
    )).send()

@cl.on_message
async def main(message: cl.Message):
    content = message.content.strip()
    content_lower = content.lower()

    # Add command
    if content_lower.startswith("add "):
        parts = content.split()
        if len(parts) >= 3:
            category = parts[1]
            amount = parts[2]
            reply = log_expense(category, amount)
            await cl.Message(content=reply).send()
            return
        else:
            await cl.Message(content="❌ Use: Add [category] [amount]").send()
            return

    # Edit command
    if content_lower.startswith("edit "):
        parts = content.split()
        if len(parts) >= 4 and parts[1].isdigit():
            row_num = int(parts[1])
            category = parts[2]
            amount = parts[3]
            reply = edit_expense(row_num, category, amount)
            await cl.Message(content=reply).send()
            return
        else:
            await cl.Message(content="❌ Use: Edit [row_number] [category] [amount]").send()
            return

    # Remove command
    if content_lower.startswith("remove "):
        parts = content.split()
        if len(parts) >= 2 and parts[1].isdigit():
            row_num = int(parts[1])
            reply = remove_expense(row_num)
            await cl.Message(content=reply).send()
            return
        else:
            await cl.Message(content="❌ Use: Remove [row_number]").send()
            return

    # Show command
    if content_lower == "show":
        reply = show_expenses()
        await cl.Message(content=reply).send()
        return

    # Regular chatbot
    agent = cast(Agent, cl.user_session.get("agent"))
    config = cast(RunConfig, cl.user_session.get("config"))
    history = cl.user_session.get("chat_history") or []
    history.append({"role": "user", "content": content})

    result = Runner.run_sync(
        starting_agent=agent,
        input=history,
        run_config=config
    )
    response_content = result.final_output
    await cl.Message(content=response_content).send()
    cl.user_session.set("chat_history", result.to_input_list())

