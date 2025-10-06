"""Rename phone fields to phone_number for consistency

Revision ID: dd57a99f2a75
Revises: 9537dc0f5036
Create Date: 2025-10-06 10:24:04.278044

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dd57a99f2a75'
down_revision = '9537dc0f5036'
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Drop all foreign key constraints first
    with op.batch_alter_table('delivery_receipts', schema=None) as batch_op:
        batch_op.drop_constraint('delivery_receipts_user_phone_fkey', type_='foreignkey')
    
    with op.batch_alter_table('events_inbound', schema=None) as batch_op:
        batch_op.drop_constraint('events_inbound_user_phone_fkey', type_='foreignkey')
    
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.drop_constraint('messages_recipient_phone_fkey', type_='foreignkey')
        batch_op.drop_index('idx_messages_recipient_phone')
    
    with op.batch_alter_table('subscriptions', schema=None) as batch_op:
        batch_op.drop_constraint('subscriptions_user_phone_fkey', type_='foreignkey')
    
    # Step 2: Rename users.phone_number to users.phone_number
    op.alter_column('users', 'phone_number', new_column_name='phone_number')
    
    # Step 3: Rename other tables' phone columns and copy data
    op.alter_column('delivery_receipts', 'user_phone', new_column_name='phone_number') 
    op.alter_column('events_inbound', 'user_phone', new_column_name='phone_number')
    op.alter_column('messages', 'recipient_phone', new_column_name='phone_number')
    op.alter_column('subscriptions', 'user_phone', new_column_name='phone_number')
    
    # Step 4: Recreate foreign key constraints  
    with op.batch_alter_table('delivery_receipts', schema=None) as batch_op:
        batch_op.create_foreign_key(None, 'users', ['phone_number'], ['phone_number'])
    
    with op.batch_alter_table('events_inbound', schema=None) as batch_op:
        batch_op.create_foreign_key(None, 'users', ['phone_number'], ['phone_number'])
    
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.create_foreign_key(None, 'users', ['phone_number'], ['phone_number'])
        batch_op.create_index('idx_messages_phone_number', ['phone_number'], unique=False)
    
    with op.batch_alter_table('subscriptions', schema=None) as batch_op:
        batch_op.create_foreign_key(None, 'users', ['phone_number'], ['phone_number'])

    # ### end Alembic commands ###


def downgrade():
    # Reverse the upgrade process
    # Step 1: Drop foreign keys
    with op.batch_alter_table('delivery_receipts', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
    
    with op.batch_alter_table('events_inbound', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
    
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_index('idx_messages_phone_number')
    
    with op.batch_alter_table('subscriptions', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
    
    # Step 2: Rename columns back to original names
    op.alter_column('delivery_receipts', 'phone_number', new_column_name='user_phone')
    op.alter_column('events_inbound', 'phone_number', new_column_name='user_phone') 
    op.alter_column('messages', 'phone_number', new_column_name='recipient_phone')
    op.alter_column('subscriptions', 'phone_number', new_column_name='user_phone')
    op.alter_column('users', 'phone_number', new_column_name='phone_number')
    
    # Step 3: Recreate foreign keys with original names
    with op.batch_alter_table('delivery_receipts', schema=None) as batch_op:
        batch_op.create_foreign_key('delivery_receipts_user_phone_fkey', 'users', ['user_phone'], ['phone_number'])
    
    with op.batch_alter_table('events_inbound', schema=None) as batch_op:
        batch_op.create_foreign_key('events_inbound_user_phone_fkey', 'users', ['user_phone'], ['phone_number'])
    
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.create_foreign_key('messages_recipient_phone_fkey', 'users', ['recipient_phone'], ['phone_number'])
        batch_op.create_index('idx_messages_recipient_phone', ['recipient_phone'], unique=False)
    
    with op.batch_alter_table('subscriptions', schema=None) as batch_op:
        batch_op.create_foreign_key('subscriptions_user_phone_fkey', 'users', ['user_phone'], ['phone_number'])
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f('delivery_receipts_user_phone_fkey'), 'users', ['user_phone'], ['phone_number'])
        batch_op.drop_column('phone_number')

    # ### end Alembic commands ###
