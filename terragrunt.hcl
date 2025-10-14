locals {
  region_vars = read_terragrunt_config(find_in_parent_folders("region.hcl", "dont_exist.hcl"), {locals = {}})
}

remote_state {
  backend = "s3"
  config = {
    bucket         = "storage-s3-iwgh-tfstate"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = "ap-southeast-1"
    encrypt        = true
    dynamodb_table = "storage-ddb-iwgh-tflock"
  }
}

inputs = merge(
  local.region_vars.locals
)

terraform {
}