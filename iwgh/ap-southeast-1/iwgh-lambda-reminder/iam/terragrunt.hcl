terraform{
    source = "git@github.com:Incandescere/iac-modules.git//iam"
}

include "root" {
    path = find_in_parent_folders()
}

locals {
    account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
    project_name = local.account_vars.locals.project_name
}

inputs = {
    name = "reminder"
    project_name = local.project_name
    policy_service_list = [
        "cloudwatch", 
        "secretsmanager"
    ]
    aws_managed_policy_arns = [
        "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
    ]   
}
