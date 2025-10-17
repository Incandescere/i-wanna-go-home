terraform{
    # source = "git@github.com:Incandescere/iac-modules.git//eventbridge-scheduler"
    source = "../../../../../iac-modules/eventbridge-scheduler"
}

include "root" {
    path = find_in_parent_folders()
}

dependency eb_role {
    config_path = "../iam"
}

dependency subscription_lambda {
    config_path = "../../iwgh-lambda-subscription/lambda"
}

locals {
    account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
    project_name = local.account_vars.locals.project_name
}

inputs = {
    name = "subscription"
    project_name = local.project_name
    schedule_expression = "rate(1 hour)"
    target_arn = dependency.subscription_lambda.outputs.zip_arn[0]
    role_arn = dependency.eb_role.outputs.arn
}
