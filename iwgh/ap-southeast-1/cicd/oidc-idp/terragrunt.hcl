terraform{
    source = "git@github.com:Incandescere/iac-modules.git//iam-oidc-idp"
}

include "root" {
    path = find_in_parent_folders()
}

locals {
    account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
    project_name = local.account_vars.locals.project_name
}

inputs = {
    url       = "token.actions.githubusercontent.com"
    audiences = ["sts.amazonaws.com"]
}