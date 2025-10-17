terraform{
    source = "git@github.com:Incandescere/iac-modules.git//iam-role"
}

include "root" {
    path = find_in_parent_folders()
}

locals {
    account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
    project_name = local.account_vars.locals.project_name
}

inputs = {
    name = "eb-lambda-invoke"
    project_name = local.project_name

    #Permissions 
    #Logging + secretsmanager read only access
    policy_service_list = [
        "cloudwatch:*",
        "lambda:InvokeFunction"
    ]

    # Allow lambda to assume this role
    services_assuming_role = [
        "scheduler.amazonaws.com"
    ]
}
