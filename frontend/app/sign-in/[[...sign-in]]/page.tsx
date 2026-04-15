import { SignIn } from "@clerk/nextjs";

export default function Page() {
  return (
    <div className="flex items-center justify-center h-screen bg-zinc-50 dark:bg-[#08090a]">
      <SignIn />
    </div>
  );
}