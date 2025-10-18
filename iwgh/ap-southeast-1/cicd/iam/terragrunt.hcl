terraform{
    source = "git@github.com:Incandescere/iac-modules.git//iam-role"
}

include "root" {
    path = find_in_parent_folders()
}

dependency oidc_idp {
    config_path = "../oidc-idp"
}

locals {
    account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
    project_name = local.account_vars.locals.project_name
}

inputs = {
    name = "lambda-update"
    project_name = local.project_name

    #Permissions
    aws_managed_policy_arns = [
        "arn:aws:iam::aws:policy/SecretsManagerReadWrite",
        "arn:aws:iam::aws:policy/AWSLambda_FullAccess"
    ]

    #Allow OIDC IDP to assume this role
    oidc_assuming_role = [{
        provider_arn = dependency.oidc_idp.outputs.arn
        repo = "Incandescere/i-wanna-go-home"
        branch = "main"
    }]
}