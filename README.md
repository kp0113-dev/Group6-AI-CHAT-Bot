# Project Repository - AWS Integrated Development - UAH AI Chat Bot

This repository is directly connected to the **AWS backend** for this project. Code changes made here can automatically sync with AWS Lambda functions in your personal development environment.

## Workflow Overview

To ensure that your changes are deployed correctly and isolated to your personal environment, follow the steps below:

### 1. Create Your Development Branch
- Name your branch using the format:  
  `dev-yourname`  
  Example: `dev-alex`  

This naming convention ensures that your code updates in GitHub are automatically reflected in **your own set of Lambda functions** in AWS.

### 2. Updating Existing Lambda Functions
- Any edits you make to Python files inside the `lambdas/` folder will **automatically update the corresponding Lambda functions** in your dev environment.

### 3. Creating New Lambda Functions
- To create a new Lambda, simply add a **new Python file** inside the `lambdas/` folder.  
- When you push your changes:
  - If the Lambda doesn’t exist yet, it will be **created** in your AWS dev environment and tagged with your name.
  - If it already exists, the Lambda’s code will be **updated** with your changes.
 
### 4. Deploying DynamoDB Tables
You can also deploy DynamoDB tables directly from this repository.

#### Creating a New Table
1. Inside the `dynamoDB/` directory, create a **new folder** named after the category of information you want to store.
2. In that folder, add two files:
- `table-template.json` → Defines the table schema (keys, indexes, billing mode, etc.).  
- `items.json` → Contains the items that should be inserted into the table after deployment.

Once pushed, the workflow will:  
- Create the table if it does not already exist.  
- Insert all items from `items.json`.  

#### Updating a Table
- To update an existing table, simply **edit the `items.json` file** in its folder.  
- Only that specific table will be redeployed (other tables are not affected).  
- Items in `items.json` will overwrite or add to the existing table data.  

## Key Notes
- Always work inside your own `dev-yourname` branch to avoid conflicts.  
- Do **not** push directly to `main` unless you are merging reviewed and approved changes.  
- Keep Lambda code in the `lambdas/` folder and DynamoDB definitions in the `dynamoDB/` folder.

## Example Workflow
1. Create branch:  
   ```bash
   git checkout -b dev-yourname
2. Add or update files in the `lambdas/` or `dynamoDB` directory.
3. Push changes:
   ```bash
   git push origin dev-yourname
4. Your AWS Console will update automatically.

