import type {ReactNode} from "react";
export const useUser = () => ({user:{fullName:"Alex Morgan",primaryEmailAddress:{emailAddress:"alex@example.com"}}});
export const UserButton = () => <button className="avatar" aria-label="Open user menu">AM</button>;
export const SignedIn = ({children}:{children:ReactNode}) => {void children; return null;};
export const SignedOut = ({children}:{children:ReactNode}) => children;
export const SignIn = () => <div className="card auth-card"><div className="card__content"><h2>Sign in to ScentIQ</h2><label className="label" htmlFor="email">Email address</label><input id="email" className="input" type="email"/><button className="button button--primary">Continue</button></div></div>;
export const SignUp = SignIn;
