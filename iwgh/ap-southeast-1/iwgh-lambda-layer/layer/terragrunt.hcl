terraform{
    source = "git@github.com:Incandescere/iac-modules.git//lambda-layer"
    # source = "C:/Users/bryan/Desktop/dev/iac-modules/lambda-layer"
}

include "root" {
    path = find_in_parent_folders()
}

dependency s3 {
    config_path = "../s3"
}


locals {
    account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
    project_name = local.account_vars.locals.project_name
}

inputs = {
    project_name = local.project_name
    name = "deps"
    bucket_name = dependency.s3.outputs.id
    # zip file should be built in linux env 
    zipfile_path = "iwgh-lambda-layer.zip"
}
