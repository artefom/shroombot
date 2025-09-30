# 🛡️ User Banning System - Usage Guide

This guide explains how to use the enhanced user banning system in your Telegram bot.

## 🚀 **Quick Start**

### **Method 1: Reply to Messages (Easiest)**
1. When a user sends spam, go to the admin chat
2. Find their message in the topic
3. Reply to their message with `/ban` to ban them instantly
4. Reply to their message with `/unban` to unban them

### **Method 2: Use User ID**
1. Look for the user ID shown in admin chat: `👤 User ID: 123456789`
2. Use `/ban 123456789` or `/unban 123456789` in admin chat
3. Or use CLI: `shroombot ban 123456789`

## 📱 **Telegram Commands (Admin Chat Only)**

| Command | Description | Example |
|---------|-------------|---------|
| `/ban` | Ban user by replying to their message | Reply to spam with `/ban` |
| `/ban <user_id>` | Ban user by ID | `/ban 123456789` |
| `/unban` | Unban user by replying to their message | Reply to their message with `/unban` |
| `/unban <user_id>` | Unban user by ID | `/unban 123456789` |
| `/banned` | List all banned users | `/banned` |
| `/help` | Show help for ban commands | `/help` |

## 💻 **CLI Commands**

| Command | Description | Example |
|---------|-------------|---------|
| `shroombot ban <user_id>` | Ban a user by ID | `shroombot ban 123456789` |
| `shroombot unban <user_id>` | Unban a user by ID | `shroombot unban 123456789` |
| `shroombot list-banned` | List all banned users | `shroombot list-banned` |
| `shroombot help-ban` | Show help for ban commands | `shroombot help-ban` |

## 🔍 **How to Get User IDs**

### **Automatic Display**
- When users send messages, their ID is automatically shown in admin chat
- Look for: `👤 User ID: 123456789`

### **From Admin Chat**
1. User sends a message
2. Bot forwards it to admin chat with user ID
3. Use the displayed ID for banning

### **From Topic Titles**
- User IDs are often visible in topic titles
- Use these IDs with `/ban <user_id>` or CLI commands

## 🎯 **Best Practices**

### **For Spam Prevention**
1. **Quick Response**: Use `/ban` by replying to spam messages
2. **Monitor**: Check `/banned` regularly to see banned users
3. **Review**: Use `/unban` if someone was banned by mistake

### **For Bulk Management**
1. **CLI Commands**: Use CLI for bulk operations
2. **Backup**: The ban list is saved in `banned_users.csv`
3. **Environment**: Set `BAN_FILE` environment variable for custom location

## ⚙️ **Configuration**

### **Environment Variables**
```bash
export BAN_FILE="/path/to/banned_users.csv"  # Default: "banned_users.csv"
```

### **File Location**
- Default: `banned_users.csv` in current directory
- Custom: Set via `--ban-file` option or `BAN_FILE` env var

## 🛡️ **Security Features**

- **Admin Only**: Commands only work in admin chat
- **Silent Filtering**: Banned users don't know they're banned
- **Persistent**: Ban list survives bot restarts
- **Error Handling**: Clear error messages for invalid commands

## 📝 **Examples**

### **Scenario 1: Spam User**
1. User sends spam message
2. Admin sees: `👤 User ID: 123456789`
3. Admin replies with `/ban`
4. Bot responds: `✅ User 123456789 has been banned`

### **Scenario 2: Mistake Ban**
1. Admin realizes mistake
2. Admin replies to user's message with `/unban`
3. Bot responds: `✅ User 123456789 has been unbanned`

### **Scenario 3: Check Banned Users**
1. Admin types `/banned`
2. Bot responds: `🚫 Banned users (2): 123456789, 987654321`

## 🆘 **Troubleshooting**

### **"Could not determine user ID"**
- Make sure you're replying to a user's message
- Check that the message is from a user (not admin)

### **"User was already banned"**
- User is already in the ban list
- Use `/banned` to see all banned users

### **"User was not banned"**
- User is not in the ban list
- Check the user ID is correct

## 🔄 **Migration from Old System**

If you had a previous ban system:
1. Export your old ban list
2. Import user IDs into `banned_users.csv`
3. One user ID per line
4. Restart the bot

---

**Need Help?** Use `/help` in admin chat or `shroombot help-ban` in CLI!
