terraform{
    source = "git@github.com:Incandescere/iac-modules.git//s3"
}

include "root" {
    path = find_in_parent_folders()
}

locals {
    account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
    account_no = local.account_vars.locals.account_no
    project_name = local.account_vars.locals.project_name
}

inputs = {
    account_no = local.account_no
    project_name = local.project_name
    bucket_name = "lambda-layer-files"
}
