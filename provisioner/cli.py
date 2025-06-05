# provisioner/cli.py

import time
import click
import os
import sys
import re
from pathlib import Path
import datetime
import tempfile
import logging
from provisioner.config.settings import DefaultSettings
from provisioner.state_manager import StateManager, CLUSTER_STATUS, SREARENA_STATUS
from provisioner.provisioner import CloudlabProvisioner
from provisioner.utils.ssh import SSHManager, SSHUtilError

logger = logging.getLogger(__name__)

_state_manager_instance: StateManager = None
_cloudlab_provisioner_instance: CloudlabProvisioner = None
EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

def is_valid_email(email: str) -> bool:
    return re.match(EMAIL_REGEX, email) is not None

def get_state_manager() -> StateManager:
    global _state_manager_instance
    if _state_manager_instance is None:
        _state_manager_instance = StateManager(db_path=DefaultSettings.DATABASE_PATH)
    return _state_manager_instance

def get_cloudlab_provisioner() -> CloudlabProvisioner:
    global _cloudlab_provisioner_instance
    if _cloudlab_provisioner_instance is None:
        if not DefaultSettings.CLOUDLAB_CONTEXT_PATH:
            click.echo(click.style("ERROR: CLOUDLAB_CONTEXT_PATH is not set in settings.", fg="red"))
            sys.exit(1)
        context_path = Path(os.path.expanduser(DefaultSettings.CLOUDLAB_CONTEXT_PATH))
        if not context_path.exists():
            click.echo(click.style(f"ERROR: Cloudlab context file not found at {context_path}", fg="red"))
            sys.exit(1)
        _cloudlab_provisioner_instance = CloudlabProvisioner(context_path=str(context_path))
    return _cloudlab_provisioner_instance

def _ensure_ssh_prerequisites():
    """Checks if necessary SSH configuration for the provisioner is present."""
    if not DefaultSettings.PROVISIONER_DEFAULT_SSH_USERNAME:
        click.echo(click.style("ERROR: PROVISIONER_DEFAULT_SSH_USERNAME is not correctly set in settings.py.", fg="red"))
        return False
    key_path = Path(os.path.expanduser(DefaultSettings.PROVISIONER_SSH_PRIVATE_KEY_PATH))
    if not key_path.exists():
        click.echo(click.style(f"ERROR: Provisioner's SSH private key not found at '{key_path}'. This is required for node operations.", fg="red"))
        return False
    return True

def _get_ssh_manager(hostname: str) -> SSHManager:
    """Creates an SSHManager instance after ensuring prerequisites."""
    if not _ensure_ssh_prerequisites():
        raise click.Abort() # Abort the current command
    return SSHManager(
        hostname=hostname,
        username=DefaultSettings.PROVISIONER_DEFAULT_SSH_USERNAME,
        private_key_path=DefaultSettings.PROVISIONER_SSH_PRIVATE_KEY_PATH
    )

def _format_ssh_command(login_info_entry: list) -> str:
    """Formats an SSH command string from a login_info entry."""
    # Assuming login_info format: [client_id, username_on_node, hostname, port]
    # The username_on_node (login_info_entry[1]) might be the user's Cloudlab username,
    # but for injecting keys, we usually use the provisioner's default SSH user.
    # For user access, we might want to use their Cloudlab username if different.
    # For now, let's assume the user logs in as PROVISIONER_DEFAULT_SSH_USERNAME.
    ssh_user = DefaultSettings.PROVISIONER_DEFAULT_SSH_USERNAME
    hostname = login_info_entry[2]
    port = login_info_entry[3]
    return f"ssh {ssh_user}@{hostname} -p {port}"

def _add_user_ssh_key_to_node(ssh_mgr: SSHManager, user_public_key: str, user_id_for_log: str) -> bool:
    """
    Safely adds a user's SSH public key to the authorized_keys file on a remote node.
    Returns True on success, False on failure.
    """
    hostname_for_log = ssh_mgr.hostname # Get from SSHManager instance
    try:
        # 1. Ensure .ssh directory and authorized_keys file exist with correct permissions
        logger.info(f"Setting up .ssh directory on {hostname_for_log} for user {user_id_for_log}")
        setup_cmd = "mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
        _, stderr_setup, exit_code_setup = ssh_mgr.execute_ssh_command(setup_cmd)
        if exit_code_setup != 0:
            click.echo(click.style(f"ERROR: Failed to setup .ssh directory on {hostname_for_log}: {stderr_setup}", fg="red"))
            logger.error(f"SSH setup cmd failed on {hostname_for_log} for user {user_id_for_log}: {stderr_setup}")
            return False

        # 2. Safely add the key: upload to temp file, then append, then remove temp file
        # Create a temporary local file to hold the public key
        with tempfile.NamedTemporaryFile(mode="w", delete=False, prefix="userkey_", suffix=".pub") as tmp_local_key_file:
            tmp_local_key_file.write(user_public_key + "\n") # Ensure newline
            local_key_path = tmp_local_key_file.name
        
        remote_tmp_key_path = f"/tmp/user_{user_id_for_log.split('@')[0]}_{os.path.basename(local_key_path)}" # Sanitize user_id part

        try:
            ssh_mgr.upload_file_scp(local_key_path, remote_tmp_key_path)
            
            add_key_cmd = f"cat {remote_tmp_key_path} >> ~/.ssh/authorized_keys"
            _, stderr_add, exit_code_add = ssh_mgr.execute_ssh_command(add_key_cmd)
            if exit_code_add != 0:
                click.echo(click.style(f"ERROR: Failed to append SSH key on {hostname_for_log}: {stderr_add}", fg="red"))
                logger.error(f"SSH key append failed on {hostname_for_log} for user {user_id_for_log}: {stderr_add}")
                return False
            logger.info(f"User SSH key for {user_id_for_log} added to {hostname_for_log}")
        finally:
            # Clean up remote temporary key file
            ssh_mgr.execute_ssh_command(f"rm -f {remote_tmp_key_path}")
            # Clean up local temporary key file
            os.remove(local_key_path)
        
        return True
    except SSHUtilError as e:
        click.echo(click.style(f"ERROR: SSH operation failed on {hostname_for_log} while adding key: {e}", fg="red"))
        logger.error(f"SSHUtilError on {hostname_for_log} for user {user_id_for_log}: {e}")
        return False
    except Exception as e:
        click.echo(click.style(f"ERROR: Unexpected error during SSH key injection on {hostname_for_log}: {e}", fg="red"))
        logger.error(f"Unexpected error injecting key on {hostname_for_log} for {user_id_for_log}: {e}", exc_info=True)
        return False

def _remove_user_ssh_key_from_node(ssh_mgr: SSHManager, user_public_key: str, user_id_for_log: str) -> bool:
    hostname_for_log = ssh_mgr.hostname
    operation_id = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
    logger.debug(f"Minimally attempting to remove SSH key for user {user_id_for_log} from {hostname_for_log} (OpID: {operation_id}).")

    user_public_key_cleaned = user_public_key.strip()
    if not user_public_key_cleaned:
        logger.error(f"Empty public key provided for {user_id_for_log}. Cannot remove.")
        return False

    local_pattern_path = None
    # Use a unique name for the remote temporary pattern file to avoid collisions
    remote_tmp_pattern_path = f"/tmp/keypattern_{user_id_for_log.split('@')[0]}_{operation_id}.pub"
    authorized_keys_path = "~/.ssh/authorized_keys" # Standard path
    # Temporary file on remote to hold filtered content
    authorized_keys_filtered_tmp_path = f"/tmp/authorized_keys_filtered_{operation_id}.tmp"

    try:
        # Create a local temporary file with the key to be removed (for grep -f)
        with tempfile.NamedTemporaryFile(mode="w", delete=False, prefix="keytoremove_", suffix=".pub") as tmp_f:
            tmp_f.write(user_public_key_cleaned + "\n")
            local_pattern_path = tmp_f.name

        # Upload the pattern file
        ssh_mgr.upload_file_scp(local_pattern_path, remote_tmp_pattern_path)

        # Command to filter out the key and overwrite the original file.
        # This command sequence first checks if authorized_keys exists.
        # If it exists, it filters it, then moves the filtered version back.
        # If authorized_keys does not exist, the `[ -f ... ]` check fails, and the `&&` chain stops.
        # The `|| true` after grep ensures the chain continues even if grep finds no non-matching lines.
        remove_cmd = (
            f"if [ -f {authorized_keys_path} ]; then "
            f"  grep -v -F -x -f {remote_tmp_pattern_path} {authorized_keys_path} > {authorized_keys_filtered_tmp_path} || true; "
            f"  mv {authorized_keys_filtered_tmp_path} {authorized_keys_path} && chmod 600 {authorized_keys_path}; "
            f"else "
            f"  echo 'Authorized_keys file not found, key considered absent.'; "
            f"fi"
        )
        # Note: If authorized_keys_path is a symlink, `mv` might behave differently than expected
        # depending on the OS. For standard files, this is okay.

        stdout, stderr, exit_code = ssh_mgr.execute_ssh_command(remove_cmd)

        if exit_code == 0:
            if "Authorized_keys file not found" in stdout:
                logger.info(f"Authorized_keys file not found on {hostname_for_log} for user {user_id_for_log}. Key considered absent.")
            else:
                logger.info(f"Successfully processed authorized_keys for key removal for {user_id_for_log} on {hostname_for_log}.")
            return True # Success or file not found (key absent)
        else:
            logger.error(f"Failed to execute key removal command for {user_id_for_log} on {hostname_for_log}. "
                         f"Exit code: {exit_code}, Stdout: '{stdout}', Stderr: '{stderr}'.")
            return False

    except SSHUtilError as e:
        logger.error(f"SSHUtilError during minimal key removal for {user_id_for_log} on {hostname_for_log}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during minimal key removal for {user_id_for_log} on {hostname_for_log}: {e}", exc_info=True)
        return False
    finally:
        # Clean up local temporary pattern file
        if local_pattern_path and os.path.exists(local_pattern_path):
            os.remove(local_pattern_path)
        # Best effort to clean up remote temporary files
        try:
            cleanup_remote_cmd = f"rm -f {remote_tmp_pattern_path} {authorized_keys_filtered_tmp_path}"
            ssh_mgr.execute_ssh_command(cleanup_remote_cmd)
        except Exception: # Ignore errors during remote cleanup
            pass

# --- Click Command Group ---
@click.group()
@click.option('--verbose', '-v', is_flag=True, help="Enable verbose output for some operations.")
@click.pass_context
def cli(ctx, verbose):
    """Cloudlab Cluster Provisioner CLI."""
    ctx.ensure_object(dict)
    ctx.obj['VERBOSE'] = verbose
    if verbose:
        click.echo("Verbose mode enabled for CLI.")

# --- User Commands ---
@cli.command()
@click.option('--email', required=True, help="Your unique email address for registration.")
@click.option('--ssh-key', required=True, help="Your SSH public key.")
def register(email, ssh_key):
    """Registers a new user with their email and SSH public key."""
    sm = get_state_manager()
    if not is_valid_email(email):
        click.echo(click.style("ERROR: Invalid email address format.", fg="red"))
        return

    try:
        # Basic validation of key format
        if not (ssh_key.startswith("ssh-rsa ") or \
            ssh_key.startswith("ssh-ed25519 ") or \
            ssh_key.startswith("ecdsa-sha2-nistp")): # Note the space
            click.echo(click.style("ERROR: Invalid or incomplete SSH public key format. Ensure it includes the key type (e.g., 'ssh-rsa AAA...').", fg="red"))
            return
    except Exception as e:
        click.echo(click.style(f"ERROR: Could not read SSH key file: {e}", fg="red"))
        return

    if sm.add_user(email, ssh_key):
        click.echo(click.style(f"User with email '{email}' registered successfully.", fg="green"))
    else:
        click.echo(click.style(f"User with email '{email}' might already be registered", fg="yellow"))

@cli.command()
@click.option('--email', required=True, help="Your registered email address.")
@click.option('--eval-override', is_flag=True, help="Request evaluation override for longer inactivity timeout.")
@click.pass_context
def claim(ctx, email, eval_override):
    """Claims an available cluster or requests a new one."""
    sm = get_state_manager()
    cp = get_cloudlab_provisioner()

    if not is_valid_email(email):
        click.echo(click.style("ERROR: Invalid email address format.", fg="red"))
        return

    user = sm.get_user(email)
    if not user:
        click.echo(click.style(f"ERROR: User with email '{email}' not registered. Please register first.", fg="red"))
        return

    user_claimed_count = sm.count_user_claimed_clusters(email)
    if user_claimed_count >= DefaultSettings.MAX_CLUSTERS_PER_USER:
        click.echo(click.style(f"ERROR: User '{email}' has already claimed the maximum of {DefaultSettings.MAX_CLUSTERS_PER_USER} clusters.", fg="red"))
        return

    # 1. Try to get an existing unclaimed_ready cluster
    unclaimed_clusters = sm.get_clusters_by_status(CLUSTER_STATUS.STATUS_UNCLAIMED_READY)
    if unclaimed_clusters:
        cluster_to_claim = unclaimed_clusters[0] # Simple: take the first one
        slice_name = cluster_to_claim['slice_name']
        hostname = cluster_to_claim['control_node_hostname']
        
        click.echo(f"Found available cluster: {slice_name}. Attempting to claim for '{email}'...")

        if not hostname:
            click.echo(click.style(f"ERROR: Cluster {slice_name} has no control_node_hostname. Cannot proceed with claim.", fg="red"))
            logger.error(f"Claim aborted for {slice_name}: missing control_node_hostname in DB.")
            return

        try:
            while not cp.are_nodes_ready(slice_name, experiment_info["aggregate_name"]):
                click.echo(click.style(f"Waiting for nodes to be ready on {slice_name}...", fg="yellow"))
                time.sleep(10)

            # add ssh public key to all nodes in the cluster
            for node_info in cluster_to_claim['login_info']:
                node_hostname = node_info[2]
                ssh_mgr = _get_ssh_manager(node_hostname)
                logger.info(f"Adding user SSH key to node {node_hostname} for user {email}")
                if not _add_user_ssh_key_to_node(ssh_mgr, user['ssh_public_key'], email):
                    return
            user_ssh_key_installed_flag = True

            # ssh_mgr = _get_ssh_manager(hostname)
            # logger.info(f"Adding user SSH key to node {hostname} for user {email}")
            # if not _add_user_ssh_key_to_node(ssh_mgr, user['ssh_public_key'], email):
            #     return
            # user_ssh_key_installed_flag = True
        except click.Abort:
            return

        # Extend Cloudlab duration
        now = datetime.datetime.now()
        new_duration_hours = DefaultSettings.CLAIMED_CLUSTER_DEFAULT_DURATION_HOURS
        new_cloudlab_expires_at = cluster_to_claim['cloudlab_expires_at'] # Default to old expiry
        try:
            if cp.renew_experiment(slice_name, new_duration_hours, cluster_to_claim['aggregate_name']):
                new_cloudlab_expires_at = now + datetime.timedelta(hours=new_duration_hours)
                logger.info(f"Extended Cloudlab experiment {slice_name} to {new_cloudlab_expires_at}")
            else:
                click.echo(click.style(f"WARNING: Failed to extend Cloudlab duration for {slice_name}. It may expire sooner. Current expiry: {new_cloudlab_expires_at}", fg="yellow"))
        except Exception as e:
            click.echo(click.style(f"WARNING: Error extending Cloudlab duration for {slice_name}: {e}. Current expiry: {new_cloudlab_expires_at}", fg="yellow"))

        # Update DB
        sm.update_cluster_record(
            slice_name,
            status=CLUSTER_STATUS.STATUS_CLAIMED,
            claimed_by_user_id=email,
            user_ssh_key_installed=user_ssh_key_installed_flag,
            cloudlab_expires_at=new_cloudlab_expires_at,
            evaluation_override=eval_override
        )
        click.echo(click.style(f"Cluster '{slice_name}' successfully claimed by '{email}'.", fg="green"))
        click.echo("SSH Access (Control Node):")
        if cluster_to_claim.get('login_info'):
            for node_info in cluster_to_claim['login_info']:
                click.echo(f"  {_format_ssh_command(node_info)}")
        elif hostname: # Fallback if login_info is missing/malformed but hostname exists
            click.echo(f"  ssh {DefaultSettings.PROVISIONER_DEFAULT_SSH_USERNAME}@{hostname}")
        else:
            click.echo(click.style("  Could not determine SSH access details.", fg="yellow"))

    else: # No UNCLAIMED_READY clusters, try to provision a new one for the user
        click.echo("No readily available clusters. Attempting to provision a new one for you...")
        
        current_total_managed = sm.count_total_managed_clusters()
        if current_total_managed >= DefaultSettings.MAX_TOTAL_CLUSTERS:
            click.echo(click.style(f"ERROR: Maximum total clusters ({DefaultSettings.MAX_TOTAL_CLUSTERS}) reached. Cannot provision for user '{email}' at this time.", fg="red"))
            return

        slice_name = cp.generate_slice_name()
        click.echo(f"Requesting new cluster: {slice_name} (this may take several minutes)...")

        # Create DB record first, marking it as user-provisioning and pre-assigning to user
        sm.create_cluster_record(
            slice_name=slice_name,
            aggregate_name="<PENDING>",
            os_type=DefaultSettings.DEFAULT_OS_TYPE,
            node_count=DefaultSettings.DEFAULT_NODE_COUNT,
            status=CLUSTER_STATUS.STATUS_USER_PROVISIONING,
            claimed_by_user_id=email, # Pre-claim
            evaluation_override=eval_override
        )
        
        experiment_info = None
        try:
            user_provision_duration = DefaultSettings.CLAIMED_CLUSTER_DEFAULT_DURATION_HOURS
            experiment_info = cp.create_experiment(
                slice_name=slice_name,
                hardware_type=DefaultSettings.DEFAULT_HARDWARE_TYPE,
                os_type=DefaultSettings.DEFAULT_OS_TYPE,
                node_count=DefaultSettings.DEFAULT_NODE_COUNT,
                duration=user_provision_duration
            )

            if not (experiment_info and experiment_info.get("login_info")):
                raise Exception("Cloudlab experiment creation failed or returned no login_info.")

            control_node_info = next((n for n in experiment_info["login_info"] if n[0] == "control"), None)
            if not control_node_info:
                raise ValueError("Control node info not found in login_info after user provisioning.")
            hostname = control_node_info[2]
            now = datetime.datetime.now()
            expires_at = now + datetime.timedelta(hours=experiment_info["duration"])

            while not cp.are_nodes_ready(slice_name, experiment_info["aggregate_name"]):
                click.echo(click.style(f"Waiting for nodes to be ready on {slice_name}...", fg="yellow"))
                time.sleep(10)

            try:
                 # add ssh public key to all nodes in the cluster
                for node_info in experiment_info['login_info']:
                    node_hostname = node_info[2]
                    ssh_mgr = _get_ssh_manager(node_hostname)
                    logger.info(f"Adding user SSH key to node {node_hostname} for user {email}")
                    if not _add_user_ssh_key_to_node(ssh_mgr, user['ssh_public_key'], email):
                        return
                user_ssh_key_installed_flag = True

                # ssh_mgr = _get_ssh_manager(hostname)
                # if not _add_user_ssh_key_to_node(ssh_mgr, user['ssh_public_key'], email):
                #     raise SSHUtilError("Failed to add user SSH key to newly provisioned cluster.")
                # user_ssh_key_installed_flag = True
            except (SSHUtilError, click.Abort) as e_ssh: # Catch Abort from _get_ssh_manager
                click.echo(click.style(f"ERROR: SSH operation failed for new cluster {slice_name}: {e_ssh}", fg="red"))
                sm.update_cluster_record(slice_name, status=CLUSTER_STATUS.STATUS_ERROR, last_error_message=f"SSH key injection failed: {e_ssh}")
                if experiment_info.get("aggregate_name"): # Attempt cleanup
                    # Mark the experiment for termination
                    logger.info(f"Marking experiment {slice_name} for termination")
                    sm.update_cluster_record(slice_name, status=CLUSTER_STATUS.STATUS_TERMINATING)
                return

            # (Placeholder) SRE Arena Setup for user-provisioned cluster
            # For now, assume success or not attempted. Daemon handles SRE for auto-provisioned.
            sre_arena_status_val = SREARENA_STATUS.SRE_ARENA_NOT_ATTEMPTED # Or SUCCESS if you run it here

            sm.update_cluster_record(
                slice_name,
                status=CLUSTER_STATUS.STATUS_CLAIMED,
                aggregate_name=experiment_info["aggregate_name"],
                hardware_type=experiment_info["hardware_type"],
                control_node_hostname=hostname,
                login_info=experiment_info["login_info"],
                user_ssh_key_installed=user_ssh_key_installed_flag,
                sre_arena_setup_status=sre_arena_status_val,
                cloudlab_expires_at=expires_at,
                claimed_at=now
            )
            click.echo(click.style(f"New cluster '{slice_name}' successfully provisioned and claimed by '{email}'.", fg="green"))
            click.echo("SSH Access (Control Node):")
            if experiment_info.get('login_info'):
                 for node_info in experiment_info['login_info']:
                    if node_info[0] == "control":
                        click.echo(f"  {_format_ssh_command(node_info)}")
            elif hostname:
                 click.echo(f"  ssh {DefaultSettings.PROVISIONER_DEFAULT_SSH_USERNAME}@{hostname}")


        except Exception as e:
            click.echo(click.style(f"ERROR: An unexpected error occurred during user-triggered provisioning for {slice_name}: {e}", fg="red"))
            logger.error(f"User provision error for {slice_name}: {e}", exc_info=True)
            # Ensure status is ERROR if it was created in DB
            if sm.get_cluster_by_slice_name(slice_name):
                 sm.update_cluster_record(slice_name, status=CLUSTER_STATUS.STATUS_ERROR, last_error_message=str(e))
            # Attempt to delete from Cloudlab if experiment_info was partially obtained
            if experiment_info and experiment_info.get("aggregate_name"):
                logger.info(f"Attempting to cleanup partially provisioned Cloudlab experiment {slice_name} (user-triggered)")
                # Mark the experiment for termination
                sm.update_cluster_record(slice_name, status=CLUSTER_STATUS.STATUS_TERMINATING)

@cli.command(name="list")
@click.option('--email', help="List clusters claimed by this email. If not provided, lists unclaimed ready clusters.")
@click.pass_context
def list_clusters(ctx, email):
    """Lists clusters. Shows unclaimed ready, or user's claimed clusters."""
    sm = get_state_manager()
    verbose = ctx.obj.get('VERBOSE', False)

    if email:
        if not is_valid_email(email):
            click.echo(click.style("ERROR: Invalid email address format.", fg="red"))
            return
        user = sm.get_user(email)
        if not user:
            click.echo(click.style(f"ERROR: User with email '{email}' not registered.", fg="red"))
            return
        clusters = sm.get_claimed_clusters_by_user(email)
        if not clusters:
            click.echo(f"User '{email}' has no claimed clusters.")
            return
        click.echo(f"Clusters claimed by '{email}':")
    else:
        clusters = sm.get_clusters_by_status(CLUSTER_STATUS.STATUS_UNCLAIMED_READY)
        if not clusters:
            click.echo("No unclaimed ready clusters available.")
            return
        click.echo("Unclaimed Ready Clusters:")

    for cluster in clusters:
        click.echo(f"  Slice: {cluster['slice_name']} (Status: {cluster['status']})")
        if verbose or email: # Show more details if verbose or listing user's clusters
            if cluster.get('control_node_hostname'):
                click.echo(f"    Control Node: {cluster['control_node_hostname']}")
            if cluster.get('cloudlab_expires_at'):
                expires_at_str = cluster['cloudlab_expires_at'].strftime('%Y-%m-%d %H:%M:%S %Z') if isinstance(cluster['cloudlab_expires_at'], datetime.datetime) and cluster['cloudlab_expires_at'].tzinfo else str(cluster['cloudlab_expires_at'])
                click.echo(f"    Cloudlab Expires: {expires_at_str}")
            if cluster.get('login_info') and isinstance(cluster.get('login_info'), list):
                 for node_info in cluster['login_info']:
                    if node_info[0] == "control":
                        click.echo(f"    SSH: {_format_ssh_command(node_info)}")
        if verbose: # Even more details for verbose mode
            click.echo(f"    Aggregate: {cluster.get('aggregate_name')}")
            click.echo(f"    Hardware: {cluster.get('hardware_type')}")
            click.echo(f"    Claimed by: {cluster.get('claimed_by_user_id', 'N/A')}")
            click.echo(f"    SRE Arena: {cluster.get('sre_arena_setup_status', 'N/A')}")


@cli.command()
@click.option('--email', required=True, help="Your registered email address.")
@click.option('--experiment', required=True, help="The name of the experiment to relinquish.")
def relinquish(email, experiment):
    """Relinquishes a claimed cluster, marking it for termination."""
    try:
        sm = get_state_manager()
        if not is_valid_email(email):
            click.echo(click.style("ERROR: Invalid email address format.", fg="red"))
            return

        user = sm.get_user(email)
        if not user:
            click.echo(click.style(f"ERROR: User with email '{email}' not registered.", fg="red"))
            return

        cluster = sm.get_cluster_by_slice_name(experiment)
        if not cluster:
            click.echo(click.style(f"ERROR: Cluster '{experiment}' not found.", fg="red"))
            return

        if cluster['claimed_by_user_id'] != email or cluster['status'] != CLUSTER_STATUS.STATUS_CLAIMED:
            click.echo(click.style(f"ERROR: Cluster '{experiment}' is not currently claimed by user '{email}'.", fg="red"))
            return
        
        try:
            ssh_mgr = _get_ssh_manager(cluster['control_node_hostname'])
            if not _remove_user_ssh_key_from_node(ssh_mgr, user['ssh_public_key'], email):
                raise SSHUtilError("Failed to remove user SSH key from relinquished cluster.")
            logger.info(f"Successfully removed user SSH key from relinquished cluster {experiment}")
        except (SSHUtilError, click.Abort) as e_ssh:
            click.echo(click.style(f"ERROR: SSH operation failed for relinquished cluster {experiment}: {e_ssh}", fg="red"))
            return

        sm.update_cluster_record(
            experiment,
            status=CLUSTER_STATUS.STATUS_TERMINATING,
            claimed_by_user_id=None, # Disassociate user
            user_ssh_key_installed=False # Mark as removed, though actual removal from node is skipped
        )
        click.echo(click.style(f"Cluster '{experiment}' relinquished by '{email}' and marked for termination.", fg="green"))
        logger.info(f"User {email} relinquished cluster {experiment}. Marked for termination.")
    except Exception as e:
        click.echo(click.style(f"ERROR: Failed to update cluster '{experiment}' status to terminating: {e}", fg="red"))
        logger.error(f"Failed to update cluster '{experiment}' status to terminating: {e}")


@cli.command()
@click.option('--experiment', required=True, help="The name of the experiment to get status for.")
def status(experiment):
    """Shows detailed status of a specific cluster."""
    sm = get_state_manager()
    cluster = sm.get_cluster_by_slice_name(experiment)
    if not cluster:
        click.echo(click.style(f"ERROR: Cluster '{experiment}' not found.", fg="red"))
        return

    click.echo(f"Status for Experiment: {click.style(cluster['slice_name'], bold=True)}")
    for key, value in sorted(cluster.items()): # Sort for consistent output
        if key == 'id': continue # Skip internal DB id
        
        display_key = key.replace('_', ' ').title()
        display_value = value

        if isinstance(value, datetime.datetime):
            display_value = value.strftime('%Y-%m-%d %H:%M:%S %Z') if value.tzinfo else value.isoformat()
        elif key == 'login_info' and isinstance(value, list):
            click.echo(f"  {display_key}:")
            for node_entry in value:
                # Assuming node_entry is [client_id, user_on_node, hostname, port]
                if node_entry[0] == "control":
                    click.echo(f"    - Control Node SSH: {_format_ssh_command(node_entry)}")
                else:
                    click.echo(f"    - {node_entry[0]}: {node_entry[2]}:{node_entry[3]}") # client_id: hostname:port
            continue # Skip default print for login_info
        elif value is None:
            display_value = click.style("N/A", dim=True)
        
        click.echo(f"  {display_key + ':':<30} {display_value}")


# --- Admin Commands ---
@cli.group()
@click.pass_context
def admin(ctx):
    """Administrative commands (use with caution)."""
    # Could add an admin check here (e.g., check user ID against a list of admins)
    # For now, relies on user discretion.
    if not ctx.obj.get('VERBOSE'): # Suggest verbose for admin commands
        click.echo(click.style("INFO: Consider using --verbose with admin commands for more details.", dim=True))
    pass

@admin.command(name="list-all")
def admin_list_all():
    """Lists ALL clusters in the database with full details."""
    sm = get_state_manager()
    clusters = sm.get_all_clusters() # Assumes get_all_clusters() exists and returns list of dicts
    if not clusters:
        click.echo("No clusters found in the database.")
        return
    
    click.echo(click.style("All Clusters in Database:", bold=True))
    for i, cluster in enumerate(clusters):
        click.echo(f"\n--- Cluster {i+1} ---")
        for key, value in sorted(cluster.items()):
            display_key = key.replace('_', ' ').title()
            display_value = value
            if isinstance(value, datetime.datetime):
                display_value = value.strftime('%Y-%m-%d %H:%M:%S %Z') if value.tzinfo else value.isoformat()
            elif key == 'login_info' and isinstance(value, list):
                click.echo(f"  {display_key}:")
                for node_entry in value:
                    click.echo(f"    - {node_entry}") # Raw print for admin
                continue
            elif value is None:
                display_value = click.style("N/A", dim=True)

            click.echo(f"  {display_key + ':':<30} {display_value}")
    click.echo("\n" + "="*30)


# --- Main Execution ---
if __name__ == '__main__':
    cli(obj={})