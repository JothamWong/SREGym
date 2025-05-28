# Getting CloudLab Credentials

1. Go to https://www.cloudlab.us/
2. Login with your cloudlab account
3. On the top right corner, click on your username, and then click on "Download Credentials"
4. This will take you to a page with a button to download the credentials. Click on it.
5. This will download a file called `cloudlab.pem`.

The `cloudlab.pem` contains the encrypted private key to your cloudlab account and ssl certificate. You need to decrypt it before using it.

```bash
sudo apt install openssl
brew install openssl
```

```bash
openssl rsa -in cloudlab.pem -out cloudlab_decrypted.pem
```
This will prompt to enter password. Then enter the password to your cloudlab account (login one)

So, now the decrypted private key will be in `cloudlab_decrypted.pem`.


# Fixing the geni-lib library

The `geni-lib` is outdated and some parts of the code are not compatible with python 3.12.

To fix this, we need to run the following script:

```bash
./scripts/geni-lib/fix_geni_lib.sh
```
Make sure to create a virtual environment and run `uv sync` before running this script.

# Building a context definition for use with Cloudlab
Now we need to build a context definition for use with Cloudlab.

```bash
build-context --type cloudlab --cert <path_to_cert> --pubkey <path_to_pubkey> --project <project_name>
```

Use small case for the project name. Otherwise, can get name conflict as Slice URNs use lowercase project name.

In this case, the command would be:

```bash
build-context --type cloudlab --cert cloudlab.pem --key cloudlab_decrypted.pem --pubkey ~/.ssh/id_ed25519.pub --project aiopslab
```

# How GENI Works

GENI (Global Environment for Network Innovations) and CloudLab use two core concepts for managing experimental resources:

## Understanding Slices and Slivers

### Slice
- A slice is a logical container that groups resources (nodes, links) for a specific experiment
- Think of it as a virtual workspace for organizing resources

### Sliver
- A sliver is a specific allocated resource (node, link, VM) within a slice
- Each sliver exists at a particular physical site (aggregate)
- Examples: A compute node at Wisconsin CloudLab
- Slivers include details like:
  - Node specifications (e.g., c220g5)
  - IP addresses (public and private)
  - SSH access information

## Using the GENI Manager

The `genictl.py` script provides an interactive CLI to manage both slices and slivers.

### Interactive Mode

Run the script to enter interactive mode:
```bash
python genictl.py
```

The CLI provides:
- Command auto-completion (press TAB to see available commands)
- Command history (use up/down arrow keys)
- Standard editing capabilities (left/right arrows, backspace, delete)
- Help system (type 'help', '-h', or '--help')

Available commands:
- `create-slice`: Create a new slice
- `create-sliver`: Create a sliver in a slice
- `sliver-status`: Check sliver status
- `renew-slice`: Extend slice expiration
- `renew-sliver`: Extend sliver expiration
- `list-slices`: List all active slices
- `sliver-spec`: View sliver specifications
- `delete-sliver`: Delete a sliver

Type 'exit' or 'q' to quit the interactive mode.

### Available Commands

1. **create-slice**
   - Creates a new slice container for your experiment
   ```
   > create-slice
   Enter slice name: test-slice
   Enter expiration time (hours from now, default 1): 24
   Enter slice description (default "CloudLab experiment"): My distributed experiment
   ```

2. **create-sliver**
   - Allocates resources in a specific site
   - Saves login information to `<slice_name>.login.info.txt`
   ```
   > create-sliver
   Enter site (utah, clemson, wisconsin): utah
   Enter slice name: test-slice
   Enter path to RSpec file: rspecs/test.xml
   ```

3. **sliver-status**
   - Checks the current status of allocated resources
   ```
   > sliver-status
   Enter site (utah, clemson, wisconsin): utah
   Enter slice name: test-slice
   ```

4. **renew-slice**
   - Extends the expiration time of a slice
   ```
   > renew-slice
   Enter slice name: test-slice
   Enter new expiration time (hours from now, default 1): 3
   ```

5. **renew-sliver**
   - Extends the expiration time of resources at a specific site
   ```
   > renew-sliver
   Enter site (utah, clemson, wisconsin): utah
   Enter slice name: test-slice
   Enter new expiration time (hours from now, default 1): 2
   ```
Sliver's expiration time cannot be greater than the slice's expiration time. So, even trying to renew both for 3h with a little delay between the commands will fail. So, make the sliver's expiration a little less than the slice's expiration time to account for the command delay. For, example, 2.9 instead of 3.

6. **list-slices**
   - Shows all active slices and their details
   ```
   > list-slices
   Output in JSON format? (y/n): n
   ```

7. **sliver-spec**
   - Shows detailed specifications of allocated resources to a slice
   - Includes node specs, IP addresses, and network info
   ```
   > sliver-spec
   Enter site (utah, clemson, wisconsin): utah
   Enter slice name: test-slice
   ```

8. **delete-sliver**
   - Removes allocated resources from a slice
   ```
   > delete-sliver
   Enter site (utah, clemson, wisconsin): utah
   Enter slice name: test-slice
   ```

