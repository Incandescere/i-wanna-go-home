terraform{
    # source = "git@github.com:Incandescere/iac-modules.git//lambda"
    source = "../../../../../iac-modules/lambda"
}

include "root" {
    path = find_in_parent_folders()
}

dependency exe_role {
    config_path = "../iam"
}

dependency eb_invoke_role {
    config_path = "../../eventbridge-scheduler/iam"
}

dependency reminder_lambda {
    config_path = "../../iwgh-lambda-reminder/lambda"
}

dependency layers {
    config_path = "../../iwgh-lambda-layer/layer"
}

locals {
    account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
    project_name = local.account_vars.locals.project_name
}

inputs = {
    name = "subscription"
    project_name = local.project_name
    execution_role_arn = dependency.exe_role.outputs.arn
    filename = "subscription.zip"
    handler = "subscription.handler"
    layers = [dependency.layers.outputs.arn]
    env_vars = {
        "reminderEbTargetArn": dependency.reminder_lambda.outputs.zip_arn[0]
        "reminderEbTargetRoleArn": dependency.eb_invoke_role.outputs.arn
    }    
}
