terraform{
    # source = "git@github.com:Incandescere/iac-modules.git//lambda"
    # source = "C:/Users/bryan/Desktop/dev/iac-modules/lambda"
    source = "../../../../../iac-modules/lambda"
}

include "root" {
    path = find_in_parent_folders()
}

dependency exe_role {
    config_path = "../iam"
}

dependency layers {
    config_path = "../../iwgh-lambda-layer/layer"
}

locals {
    account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
    project_name = local.account_vars.locals.project_name
}

inputs = {
    name = "reminder"
    project_name = local.project_name
    execution_role_arn = dependency.exe_role.outputs.arn
    filename = "reminder.zip"
    handler = "reminder.handler"
    layers = [dependency.layers.outputs.arn]
}
