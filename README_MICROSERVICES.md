# Account & Login Microservices Communication

This setup demonstrates communication between the Account microservice and Login microservice.

## Architecture

- **Login Service**: Manages users (port 8001)
- **Account Service**: Manages accounts and transactions (port 8002)
- **Communication**: Account service calls Login service to validate users

## Quick Start

### Option 1: Run Both Services with Docker Compose

1. **Ensure both services are in the same parent directory:**
   ```
   parent-folder/
   ├── login-microservice/
   └── Account-Microservice/
   ```

2. **Run both services:**
   ```bash
   cd Account-Microservice
   docker-compose -f docker-compose.multi.yml up --build
   ```

3. **Test the communication:**
   ```bash
   python test_communication.py
   ```

### Option 2: Run Services Separately

1. **Start Login Service:**
   ```bash
   cd ../login-microservice
   docker-compose up --build
   ```

2. **Start Account Service:**
   ```bash
   cd ../Account-Microservice
   docker-compose up --build
   ```

3. **Test communication:**
   ```bash
   python test_communication.py
   ```

## Service Endpoints

### Login Service (http://localhost:8001)
- `POST /api/users` - Create user
- `GET /api/users/{user_id}` - Get user details
- `GET /api/users` - List all users

### Account Service (http://localhost:8002)
- `POST /accounts/from-user/{user_id}` - Create account for user
- `GET /accounts/by-user/{user_id}` - Get account by user ID
- `GET /accounts/by-user/{user_id}/details` - Get account + user details
- `POST /accounts/by-number/{account_number}/deposit` - Deposit money
- `POST /accounts/by-number/{account_number}/withdraw` - Withdraw money
- `POST /accounts/by-number/{account_number}/transfer` - Transfer money

## Communication Flow

1. **Create User**: POST to Login service creates a user
2. **Create Account**: POST to Account service with user_id
   - Account service calls Login service to validate user exists
   - Creates account linked to user_id
3. **Get Details**: Account service fetches user details from Login service
4. **Delete Cascade**: When user is deleted from Login, it notifies Account service

## Environment Configuration

### Development (.env.dev)
- Login Service: `http://localhost:8001`
- Account Service: `http://localhost:8002`

### Docker (.env.docker)
- Login Service: `http://login:8000` (internal)
- Account Service: `http://account:8000` (internal)

## Testing

Run the test script to verify communication:
```bash
python test_communication.py
```

This will:
1. Create a user in Login service
2. Create an account for that user in Account service
3. Test communication by fetching combined user+account details
4. Perform a sample transaction

## Troubleshooting

1. **Services not communicating**: Check that both services are running and ports are correct
2. **Database issues**: Ensure PostgreSQL containers are healthy
3. **Port conflicts**: Make sure ports 8001, 8002, 5433, 5434 are available