from app import app, db, User, Booking, Certificate, Reward

def sync_all_data():
    with app.app_context():
        users = User.query.all()
        for user in users:
            print(f"Syncing data for user: {user.email} (ID: {user.id})")
            
            # 1. Sync Bookings
            bookings = Booking.query.filter_by(customer_email=user.email, user_id=None).all()
            if bookings:
                print(f"  - Linking {len(bookings)} bookings")
                for b in bookings:
                    b.user_id = user.id
            
            # 2. Sync Certificates
            certs = Certificate.query.filter_by(customer_email=user.email, user_id=None).all()
            if certs:
                print(f"  - Linking {len(certs)} certificates")
                for c in certs:
                    c.user_id = user.id
                    
            # 3. Sync Rewards
            reward = Reward.query.filter_by(customer_email=user.email).first()
            if reward and reward.user_id != user.id:
                print(f"  - Linking reward record")
                reward.user_id = user.id
            elif not reward:
                print(f"  - Creating missing reward record")
                reward = Reward(user_id=user.id, customer_email=user.email, points=0)
                db.session.add(reward)
        
        db.session.commit()
        print("Global sync complete!")

if __name__ == "__main__":
    sync_all_data()
